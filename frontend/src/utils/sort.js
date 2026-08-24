/**
 * 列表排序工具
 * 实体面板与关系面板共用的名称排序规则，保证两个列表排序行为一致。
 * @author aceFelix
 */

/**
 * 名称排序比较器：按首字母升序
 * - 中文按拼音序（如"沈阳化工大学"排在"计算机科学与技术"前）
 * - 英文不区分大小写（aceFelix 与 AI Agent 按字母正常比较）
 * - 数字按自然序（Vue 3 排在 Vue 10 之前）
 * @param {string} a - 名称 A
 * @param {string} b - 名称 B
 * @returns {number} localeCompare 结果（负数 = A 排前）
 */
export function nameCompare(a, b) {
  return (a || '').localeCompare(b || '', 'zh-Hans-CN-u-co-pinyin', {
    sensitivity: 'base',
    numeric: true,
  })
}
