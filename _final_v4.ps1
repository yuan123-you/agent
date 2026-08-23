# 最终验证：向量RAG恢复 + 转人工 + 联网搜索(Tavily) + 回归
$base = "http://localhost:8080/api/v1"
$results = @()
function Add-Result($id, $name, $pass, $detail) {
  $script:results += [PSCustomObject]@{ ID = $id; Name = $name; Result = if ($pass) { "PASS" } else { "FAIL" }; Detail = $detail }
}
$r = & curl.exe -s -X POST "$base/auth/login" -H "Content-Type: application/json" -d '{\"username\":\"customer01\",\"password\":\"123456\"}'
$ct = ($r | ConvertFrom-Json).data.accessToken

# 等待限流窗口重置（每用户 20 条/分钟）
Write-Host "等待限流窗口重置(65s)..."
Start-Sleep -Seconds 65

function AskAI($id, $content, $mustInclude, $webSearch = $false) {
  $r = & curl.exe -s -X POST "$base/chat/conversations" -H "Authorization: Bearer $ct"
  $conv = ($r | ConvertFrom-Json).data.conversationId
  # PowerShell 布尔插值为 True/False（非法 JSON），转小写
  $wsJson = if ($webSearch) { 'true' } else { 'false' }
  $tmp = New-TemporaryFile
  [System.IO.File]::WriteAllText($tmp, "{`"conversationId`":$conv,`"content`":`"$content`",`"webSearchEnabled`":$wsJson}", [System.Text.Encoding]::UTF8)
  $out = & curl.exe -s -N -X POST "$base/chat/messages" -H "Authorization: Bearer $ct" -H "Content-Type: application/json" --data-binary "@$tmp" --max-time 150
  $ec = $LASTEXITCODE
  Remove-Item $tmp -ErrorAction SilentlyContinue
  $text = $out -join "`n"
  Write-Host "  [diag $id] exit=$ec lines=$($out.Count) chars=$($text.Length) done=$($text -match 'event:\s*done') err=$($text -match 'event:\s*error')"
  Start-Sleep -Seconds 4  # 避免触发对话限流（20条/分钟）
  $done = $text -match "event:\s*done"
  $toks = [regex]::Matches($text, 'data:\{"content":\s*"((?:[^"\\]|\\.)*)"\}') | ForEach-Object { $_.Groups[1].Value }
  $answer = ($toks -join "") -replace '\\n', "`n" -replace '\\"', '"'
  $hit = $true
  foreach ($kw in $mustInclude) { if ($answer -notmatch [regex]::Escape($kw)) { $hit = $false } }
  return @{ conv = $conv; ok = ($ec -eq 0 -and $done); answer = $answer; hit = $hit; text = $text }
}

# ① 向量 RAG 恢复验证（政策问答，应走向量路径且命中）
$r1 = AskAI "KB" "7天无理由退货从哪天开始算？" @("签收", "7天")
Add-Result "KB-1" "向量RAG政策问答" ($r1.ok -and $r1.hit) "命中=$($r1.hit)"
Write-Output "[KB-1] $($r1.answer.Substring(0, [Math]::Min(120, $r1.answer.Length)))..."

# ② 转人工（新按钮等价路径：发送'转人工客服'）
$r2 = AskAI "ESC" "转人工客服" @()
$esc = $r2.text -match "escalate"
# 验证会话状态变为 PENDING_HUMAN
$convState = & curl.exe -s "$base/chat/conversations/$($r2.conv)" -H "Authorization: Bearer $ct" | ConvertFrom-Json
Add-Result "ESC-1" "转人工链路(按钮等价)" ($r2.ok -and $esc -and $convState.data.status -eq "PENDING_HUMAN") "escalate=$esc status=$($convState.data.status)"

# ③ 联网搜索（Tavily 引擎，验证 web_search 工具带 engine=tavily）
$r3 = AskAI "WS" "2026年最新发布的手机有哪些" @() $true
$wsCall = $r3.text -match "web_search"
$tavily = $r3.text -match "tavily"
$mark = $r3.answer -match "联网搜索"
Add-Result "WS-1" "联网搜索(Tavily)" ($r3.ok -and $wsCall -and $mark) "tool=$wsCall tavily=$tavily 标注=$mark"
Write-Output "[WS-1] $($r3.answer.Substring(0, [Math]::Min(120, $r3.answer.Length)))..."

# ④ 商品推荐回归
$r4 = AskAI "REG" "推荐一款拍照好的手机" @("mall://product")
Add-Result "REG-1" "商品推荐回归" ($r4.ok -and $r4.hit) "链接=$($r4.hit)"

Write-Output ""
$results | Format-Table ID, Name, Result, Detail -AutoSize
$pass = ($results | Where-Object { $_.Result -eq "PASS" }).Count
Write-Output "TOTAL: $($results.Count)  PASS: $pass  FAIL: $($results.Count - $pass)"
