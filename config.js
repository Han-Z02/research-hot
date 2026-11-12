/* 科研HOT | 前沿文献雷达 — 站点配置
 * ============================================================
 * 密码门：简易密码门，不是真加密。
 * - 打开站先输密码，输对才显示内容；解锁状态只保留在当前标签页
 *   会话（sessionStorage），关掉标签页就要重输。
 * - 站里只存密码的 SHA-256 哈希，不存明文密码；密码本身绝不进仓库。
 * - 局限（必须如实告诉课题组）：data/papers.json 在仓库里仍是明文，
 *   懂行的人直接读数据文件就能绕过密码门，只防随手点开的外人。
 *   文献本身都是公开的（Europe PMC / bioRxiv），锁只是限定范围。
 *
 * 设置密码（密码原文绝不在聊天里发）：
 *   1. 在你自己的电脑上算哈希（macOS / Linux 通用）：
 *        printf '%s' '你的新密码' | shasum -a 256
 *      Windows PowerShell：
 *        (New-Object System.Security.Cryptography.SHA256Managed).ComputeHash(
 *          [Text.Encoding]::UTF8.GetBytes('你的新密码')) |
 *          ForEach-Object { $_.ToString('x2') } -join ''
 *   2. 只把算出来的 64 位十六进制哈希发给 Muse，我把它填进下面
 *      的 PASSWORD_SHA256；或者你自己直接改这个文件后提 PR。
 *   3. 哈希一旦换了，课题组需要用新密码重新解锁。
 */
window.RESEARCH_HOT_CONFIG = {
  // 占位符：替换为新密码的 SHA-256 哈希（64 位小写十六进制）。
  // 替换前站点打不开（密码门会提示“未设置密码”）。
  PASSWORD_SHA256: "REPLACE_WITH_SHA256_HASH",
  SITE_NAME: "科研HOT｜前沿文献雷达",
  DATA_URL: "data/papers.json",
  DIGEST_URL: "data/digest.json",
};
