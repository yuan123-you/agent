# 问题修复全链路验证：FAQ自动回答 / 转人工禁用AI / 客服感知关闭 / 知识库标题 / 流式
$base = "http://localhost:8080/api/v1"
$results = @()
function Add-Result($id, $name, $pass, $detail) {
  $script:results += [PSCustomObject]@{ ID = $id; Name = $name; Result = if ($pass) { "PASS" } else { "FAIL" }; Detail = $detail }
}

# 登录客户
$rc = & curl.exe -s -X POST "$base/auth/login" -H "Content-Type: application/json" -d '{\"username\":\"customer01\",\"password\":\"123456\"}'
$ct = ($rc | ConvertFrom-Json).data.accessToken
if (-not $ct) { Write-Output "customer01 登录失败"; exit 1 }
# 登录客服
$ra = & curl.exe -s -X POST "$base/auth/login" -H "Content-Type: application/json" -d '{\"username\":\"agent01\",\"password\":\"123456\"}'
$at = ($ra | ConvertFrom-Json).data.accessToken

# 新建会话
function NewConv($token) {
  $r = & curl.exe -s -X POST "$base/chat/conversations" -H "Authorization: Bearer $token"
  return ($r | ConvertFrom-Json).data.conversationId
}

# SSE 发送并返回 (text, elapsedMs)
function SendMsg($token, $conv, $content, $ws = $false) {
  $wsJson = if ($ws) { 'true' } else { 'false' }
  $tmp = New-TemporaryFile
  [System.IO.File]::WriteAllText($tmp, "{`"conversationId`":$conv,`"content`":`"$content`",`"webSearchEnabled`":$wsJson}", [System.Text.Encoding]::UTF8)
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $out = & curl.exe -s -N -X POST "$base/chat/messages" -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$tmp" --max-time 150
  $sw.Stop()
  Remove-Item $tmp -ErrorAction SilentlyContinue
  $text = $out -join "`n"
  return @{ text = $text; ms = $sw.ElapsedMilliseconds }
}

# ========== ① FAQ 关键词自动回答（不调 AI，快速返回） ==========
$conv1 = NewConv $ct
$f = SendMsg $ct $conv1 "支持7天无理由退货吗"
$faqHit = $f.text -match 'faq' -or $f.text -match 'data:\{"content"' 
# FAQ 判定：done 事件带 faq:true
$faqFlag = $f.text -match '"faq":true'
$fast = $f.ms -lt 5000
Add-Result "FAQ-1" "FAQ关键词自动回答(不调AI)" ($f.text -match 'event:\s*done' -and $faqFlag -and $fast) "耗时=$($f.ms)ms faq标志=$faqFlag"
Write-Output "[FAQ-1] $($f.ms)ms done=$($f.text -match 'event:\s*done') faq=$faqFlag"
Start-Sleep -Seconds 4

# ========== ② 转人工 → PENDING_HUMAN ==========
$e = SendMsg $ct $conv1 "转人工客服"
$state1 = (& curl.exe -s "$base/chat/conversations/$conv1/status" -H "Authorization: Bearer $ct" | ConvertFrom-Json).data.status
Add-Result "ESC-1" "转人工→PENDING_HUMAN" ($state1 -eq "PENDING_HUMAN") "status=$state1"
Start-Sleep -Seconds 4

# ========== ③ 客服接入 → SERVICING ==========
& curl.exe -s -X POST "$base/workbench/conversations/$conv1/claim" -H "Authorization: Bearer $at" | Out-Null
$state2 = (& curl.exe -s "$base/chat/conversations/$conv1/status" -H "Authorization: Bearer $ct" | ConvertFrom-Json).data.status
Add-Result "CLAIM-1" "客服接入→SERVICING" ($state2 -eq "SERVICING") "status=$state2"

# ========== ④ 买家在人工服务中发消息（必须绕过 AI 直达客服） ==========
$tmp = New-TemporaryFile
[System.IO.File]::WriteAllText($tmp, '{"content":"你好，我想问下我的订单什么时候发货"}', [System.Text.Encoding]::UTF8)
$hm = & curl.exe -s -X POST "$base/chat/conversations/$conv1/human-message" -H "Authorization: Bearer $ct" -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item $tmp -ErrorAction SilentlyContinue
$hmCode = ($hm | ConvertFrom-Json).code
Add-Result "HUMAN-1" "人工服务中买家消息直达客服" ($hmCode -eq 0) "code=$hmCode"

# ========== ⑤ AI 旁路验证：SERVICING 状态调用 AI 接口应被拒 ==========
$tmp2 = New-TemporaryFile
[System.IO.File]::WriteAllText($tmp2, "{`"conversationId`":$conv1,`"content`":`"测试AI是否禁用`"}", [System.Text.Encoding]::UTF8)
$aiBlock = & curl.exe -s -X POST "$base/chat/messages" -H "Authorization: Bearer $ct" -H "Content-Type: application/json" --data-binary "@$tmp2" --max-time 20
Remove-Item $tmp2 -ErrorAction SilentlyContinue
$aiBlocked = $aiBlock -match '2004|已转人工|无法使用AI'
Add-Result "AIBLOCK-1" "人工服务中AI完全禁用" $aiBlocked "响应=$($aiBlock.Substring(0,[Math]::Min(60,$aiBlock.Length)))"

# ========== ⑥ 客服回复 + 买家轮询可见 ==========
$tmp3 = New-TemporaryFile
[System.IO.File]::WriteAllText($tmp3, '{"content":"您好，您订单预计明天发货，请留意物流信息。"}', [System.Text.Encoding]::UTF8)
& curl.exe -s -X POST "$base/workbench/conversations/$conv1/messages" -H "Authorization: Bearer $at" -H "Content-Type: application/json" --data-binary "@$tmp3" | Out-Null
Remove-Item $tmp3 -ErrorAction SilentlyContinue
$msgs = (& curl.exe -s "$base/chat/conversations/$conv1/messages?afterId=0&size=50" -H "Authorization: Bearer $ct" | ConvertFrom-Json).data.records
$agentMsg = ($msgs | Where-Object { $_.role -eq 'AGENT' }).Count
$userMsg = ($msgs | Where-Object { $_.role -eq 'USER' -and $_.content -match '订单什么时候发货' }).Count
Add-Result "AGENT-1" "客服回复买家可见" ($agentMsg -ge 1 -and $userMsg -ge 1) "AGENT消息=$agentMsg 买家消息=$userMsg"

# ========== ⑦ 买家结束会话 → 客服端感知 CLOSED ==========
& curl.exe -s -X POST "$base/chat/conversations/$conv1/close" -H "Authorization: Bearer $ct" | Out-Null
$state3 = (& curl.exe -s "$base/chat/conversations/$conv1/status" -H "Authorization: Bearer $ct" | ConvertFrom-Json).data.status
$agentSees = (& curl.exe -s "$base/workbench/conversations/$conv1/status" -H "Authorization: Bearer $at" | ConvertFrom-Json).data.status
Add-Result "CLOSE-1" "买家结束→客服自动感知" ($state3 -eq "CLOSED" -and $agentSees -eq "CLOSED") "买家=$state3 客服=$agentSees"

# ========== ⑧ 知识库来源标题（非FAQ问题走RAG，验证无"知识库文档#X"） ==========
$conv2 = NewConv $ct
$k = SendMsg $ct $conv2 "手机质保期是多久"
$srcBad = $k.text -match '知识库文档#'
Add-Result "SRC-1" "知识库来源显示标题(非内部编号)" (-not $srcBad) "含内部编号=$srcBad"
$m = [regex]::Match($k.text, 'data:\{"content":\s*"((?:[^"\\]|\\.)*)"\}')
if ($m.Success) { Write-Output "[SRC-1] 回答片段: $($m.Groups[1].Value.Substring(0,[Math]::Min(100,$m.Groups[1].Value.Length)))..." }
Start-Sleep -Seconds 4

# ========== ⑨ 403 防护：客服 token 访问 /chat 应被拒（前端已静默+角色拦截） ==========
$forbidden = (& curl.exe -s -o NUL -w "%{http_code}" "$base/chat/conversations" -H "Authorization: Bearer $at")
Add-Result "403-1" "客服token访问/chat被拦截(403)" ($forbidden -eq "403") "http=$forbidden"

Write-Output ""
$results | Format-Table ID, Name, Result, Detail -AutoSize
$pass = ($results | Where-Object { $_.Result -eq "PASS" }).Count
Write-Output "TOTAL: $($results.Count)  PASS: $pass  FAIL: $($results.Count - $pass)"
