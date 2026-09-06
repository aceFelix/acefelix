"""
文档上传接口（POST /api/upload/doc）单元测试
覆盖扩展名白名单校验、大小限制、文件名清洗（防路径穿越）、
静态访问链路，以及图片上传接口的回归验证。

上传目录通过 mock 替换为临时目录，不污染真实 doc_uploads/。

运行: python backend/tests/test_upload_api.py （或 python -m unittest discover）

@author aceFelix
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# 测试在 tests/ 下，把 backend 根目录加入搜索路径以导入 api 模块。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _file_tuple(filename: str, content: bytes = b"hello"):
    """构造 TestClient 上传用的 (字段名, (文件名, 内容, MIME)) 三元组"""
    return {"file": (filename, content, "application/octet-stream")}


class UploadDocApiTest(unittest.TestCase):
    """文档上传接口测试：上传目录替换为临时目录"""

    def setUp(self):
        self.client = TestClient(api.app)
        self._tmpdir = tempfile.TemporaryDirectory()
        # 把模块级上传目录指向临时目录（save 时实时读取，patch 生效）
        self._patcher = mock.patch.object(
            api, "DOC_UPLOAD_DIR", Path(self._tmpdir.name)
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()

    # ---------------- 正常路径 ---------------- #

    def test_upload_all_allowed_extensions(self):
        """五种白名单扩展名（pdf/md/txt/docx/xmind）均可上传成功"""
        for ext in (".pdf", ".md", ".txt", ".docx", ".xmind"):
            with self.subTest(ext=ext):
                resp = self.client.post("/api/upload/doc", files=_file_tuple(f"note{ext}"))
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertTrue(body["url"].startswith(f"/doc-uploads/"))
                self.assertTrue(body["url"].endswith(ext))
                self.assertEqual(body["name"], f"note{ext}")

    def test_uploaded_file_persisted_with_content(self):
        """上传后文件真实落盘且内容一致，文件名保留原始名称（带短 UUID 前缀）"""
        resp = self.client.post(
            "/api/upload/doc", files=_file_tuple("简历.pdf", b"%PDF-1.4 fake")
        )
        self.assertEqual(resp.status_code, 200)
        saved = list(Path(self._tmpdir.name).iterdir())
        self.assertEqual(len(saved), 1)
        self.assertTrue(saved[0].name.endswith("_简历.pdf"))
        self.assertEqual(saved[0].read_bytes(), b"%PDF-1.4 fake")

    # ---------------- 异常路径 ---------------- #

    def test_reject_non_whitelist_extension(self):
        """非白名单扩展名（.exe/.png/无扩展名）返回 400"""
        for filename in ("virus.exe", "photo.png", "noext"):
            with self.subTest(filename=filename):
                resp = self.client.post("/api/upload/doc", files=_file_tuple(filename))
                self.assertEqual(resp.status_code, 400)
                self.assertIn("仅支持", resp.json()["detail"])

    def test_reject_oversize_document(self):
        """超过大小上限返回 400（patch 上限为 10 字节模拟）"""
        with mock.patch.object(api, "DOC_MAX_SIZE", 10):
            resp = self.client.post(
                "/api/upload/doc", files=_file_tuple("big.pdf", b"x" * 11)
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("20MB", resp.json()["detail"])

    def test_path_traversal_filename_sanitized(self):
        """恶意文件名（路径穿越/非法字符）被清洗，保存文件不逃出上传目录"""
        resp = self.client.post(
            "/api/upload/doc", files=_file_tuple("../../evil<>:.pdf", b"data")
        )
        self.assertEqual(resp.status_code, 200)
        saved = list(Path(self._tmpdir.name).iterdir())
        self.assertEqual(len(saved), 1)
        # 清洗后文件名不含路径分隔符与 Windows 非法字符
        self.assertNotIn("/", saved[0].name)
        self.assertNotIn("\\", saved[0].name)
        self.assertNotIn("<", saved[0].name)
        # 文件仍在上传目录内（未穿越）
        self.assertEqual(saved[0].parent, Path(self._tmpdir.name))


class UploadStaticServeTest(unittest.TestCase):
    """静态访问链路测试：走真实 doc_uploads 目录，测试后清理文件"""

    def setUp(self):
        self.client = TestClient(api.app)

    def test_uploaded_doc_accessible_via_static_url(self):
        """上传后通过 /doc-uploads/{filename} 可 GET 到相同内容"""
        resp = self.client.post(
            "/api/upload/doc", files=_file_tuple("readme.md", b"# title")
        )
        self.assertEqual(resp.status_code, 200)
        url = resp.json()["url"]
        saved_path = api.DOC_UPLOAD_DIR / Path(url).name
        try:
            got = self.client.get(url)
            self.assertEqual(got.status_code, 200)
            self.assertEqual(got.content, b"# title")
        finally:
            saved_path.unlink(missing_ok=True)


class UploadImageRegressionTest(unittest.TestCase):
    """图片上传接口回归：原白名单行为不受文档接口影响"""

    def setUp(self):
        self.client = TestClient(api.app)
        self._tmpdir = tempfile.TemporaryDirectory()
        self._patcher = mock.patch.object(api, "UPLOAD_DIR", Path(self._tmpdir.name))
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()

    def test_image_upload_still_works(self):
        """PNG 图片上传成功，URL 前缀为 /uploads/"""
        resp = self.client.post(
            "/api/upload",
            files={"file": ("a.png", b"\x89PNG fake", "image/png")},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["url"].startswith("/uploads/"))

    def test_image_upload_rejects_document(self):
        """文档类型仍被图片接口拒绝（MIME 白名单未放宽）"""
        resp = self.client.post(
            "/api/upload",
            files={"file": ("a.pdf", b"%PDF", "application/pdf")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("仅支持图片", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
