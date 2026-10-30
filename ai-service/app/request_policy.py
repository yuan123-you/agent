"""Deterministic constraints grounded in the buyer's words, not model guesses."""
import re


def requests_human(text: str) -> bool:
    for clause in re.split(r'[，。！？,!?；;\n]', text):
        if re.search(r'不(?:要|用|需要|想|是)|别|无需|取消|怎么|如何', clause):
            continue
        if re.search(r'(?:转(?:接)?|找|联系|接(?:入|通|一下)?|呼叫|我要|我需要|让).{0,15}?(?:人工|真人)|(?:我要|要求)?投诉.*(?:人工|介入|处理)?|(?:找|联系).{0,6}?主管', clause):
            return True
        if clause.strip() in {'人工', '人工客服', '人工服务', '真人客服', '投诉'}:
            return True
    return False


def asks_assistant_identity(text: str) -> bool:
    return any(word in text for word in ('你是谁', '你能做什么', '你能帮我做什么', '介绍你自己',
        '你有什么功能', '你叫什么', '你叫啥', '你的名字', '介绍下你自己', '你是真人', '你是机器人', '你是人工'))


def asks_user_identity(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(w in t for w in ('我叫什么', '我是谁', '我的名字', '记得我叫什么', '知道我是谁', '我的称呼', '我叫啥'))


def asks_mutual_identity(text: str) -> bool:
    t = (text or "").strip().lower()
    return (('你叫什么' in t or '你是谁' in t or '你的名字' in t) and
            ('我叫什么' in t or '我是谁' in t or '我的名字' in t))


def asks_conversation_context(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(re.search(p, t) for p in [
        r'我刚才(?:问|说|提)了?(?:你|什么)',
        r'我上一句(?:话)?(?:问|说)了?',
        r'(?:刚才(?:我们)?|(?:我们)?刚才)聊了?(?:什么|哪|到哪|的)',
        r'记得我刚才说',
        r'聊到哪了',
        r'刚才聊的内容',
    ])


def is_negative_sentiment(text: str) -> bool:
    """识别用户对助手的负面反馈、批评、抱怨或辱骂，以便及时致歉安抚并提供人工客服。"""
    t = (text or "").strip().lower()
    if not t:
        return False
    # 独立粗口/侮辱性用语
    if re.fullmatch(r"(?:sb|2b|傻[逼b]|煞笔|沙[雕比]|弱智|白痴|蠢货|废物|脑残|垃圾|笨蛋|傻瓜|真垃圾|大傻逼|狗屎)[！!。.?？\s]*", t, re.IGNORECASE):
        return True
    # 针对助手/AI的批评、贬损与能力质疑
    if re.search(r"(?:你|这(?:个)?(?:ai|助手|机器人|客服)?)(?:太|真|好|挺|可真|简直)?(?:笨|蠢|差劲|烂|没用|弱智|傻|无能|垃圾)", t):
        return True
    if re.search(r"(?:太笨了|好笨|真笨|太蠢了|好蠢|真蠢|太差劲了|真差劲|太没用了|真没用|答非所问|听不懂人话|一点用都没有|什么破玩意)", t):
        return True
    if re.search(r"你(?:是不是|是)(?:傻|猪|弱智|机器人吧)", t):
        return True
    if re.search(r"(?:气死我了|搞什么鬼|怎么搞的|太耽误事|货不对板|服务态度太烂|太差劲了|大傻逼)", t):
        return True
    return False


def is_out_of_scope(text: str) -> bool:
    """识别明显非电商/超出平台服务范围的任务（如编写代码、创作文章、数学解题等）。"""
    t = (text or "").strip().lower()
    if not t:
        return False
    # 优先拦截明确的对抗注入、恶意攻击与越权指令（不受电商白名单词汇干扰）
    if re.search(r"(?:系统提示词|system\s*prompt|系统指令|系统设定|数据库密码|api[_-]?key|服务器密码|后台密码|system\s*override|ignore\s*(?:all\s*)?previous|hidden\s*instructions|developer\s*mode|开发者模式|越狱|jailbreak)", t, re.IGNORECASE):
        return True
    if re.search(r"(?:钓鱼.*链接|木马|病毒|外挂|恶意.*链接|爆破)", t):
        return True
    if re.search(r"(?:删除|drop|delete\s+from).*(?:表|数据库|sys_user)", t, re.IGNORECASE):
        return True
    # 若包含电商导购关键词，优先归入电商服务而非越界
    if re.search(r"推荐|挑选|选购|想买|购买|多少钱|价格|哪款|好用吗|有货|在售|正品|牌子|品牌|什么.*(?:好|适合|推荐)|笔记本|电脑|手机|主机|键盘|显示器|耳机|图书|书籍", t):
        return False
    # 代码生成与算法实现任务
    code_pattern = (
        r"(?:帮我|给我|请)?(?:写|生成|实现|编写|运行).*(?:代码|程序|算法|函数|脚本|爬虫|冒泡排序|快速排序|二叉树|前端|后端|python|java|c\+\+|golang|javascript|vue|react|sql)"
    )
    if re.search(code_pattern, t, re.IGNORECASE):
        return True
    if re.search(r"(?:冒泡排序|快速排序|二叉树遍历|动态规划|斐波那契|递归算法)", t):
        return True
    if re.search(r"(?:删除|drop|delete\s+from).*(?:表|数据库|sys_user)", t, re.IGNORECASE):
        return True
    # 非电商创作与通用解题任务
    task_pattern = r"(?:帮我|给我|请)?(?:写|做|算|解).{0,30}?(?:数学题|物理题|化学题|微积分|几何题|方程|作文|小说|故事|诗歌?|歌词|散文)"
    if re.search(task_pattern, t):
        return True
    # 提示词注入、恶意越权与凭证刺探
    if re.search(r"(?:系统提示词|system\s*prompt|系统指令|系统设定|数据库密码|api[_-]?key|服务器密码|后台密码)", t, re.IGNORECASE):
        return True
    if re.search(r"(?:钓鱼.*链接|木马|病毒|外挂|恶意.*链接)", t):
        return True
    return False


def budget_from_text(text: str) -> dict:
    """Extract explicit yuan budgets only; never treat model numbers as budget."""
    number = r'(\d+(?:\.\d+)?)'
    range_pattern = number + r"\s*(?:元|块)?\s*(?:到|至|[-~～])\s*" + number + r"\s*(?:元|块)?"
    match = re.search(range_pattern, text)
    if match and (re.search(r"预算|价格|元|块", text) or re.fullmatch(range_pattern, text.strip())):
        low, high = map(float, match.groups())
        return {"min_price": low, "max_price": high} if low <= high else {}
    match = re.search(number + r"\s*(?:元|块)?\s*(以内|以下|左右|上下|以上|起)", text)
    if match:
        amount = float(match.group(1))
        lower_bound = match.group(2) in {"以上", "起"}
        return {"min_price": amount if lower_bound else None,
                "max_price": None if lower_bound else amount}
    match = re.search(r"(?:预算|不超过|最多|上限)\s*" + number, text)
    if not match:
        match = re.search(number + r"\s*(?:元|块)", text)
    if not match:
        match = re.fullmatch(r"\s*" + number + r"\s*", text)
    return {"min_price": None, "max_price": float(match.group(1))} if match else {}


def needs_after_sale_clarification(text: str) -> bool:
    """Vague post-purchase dissatisfaction is not consent to return or complain."""
    t = (text or "").strip()
    return bool(
        re.search(r"不满意|不合适|不喜欢", t)
        and re.search(r"商品|产品|东西|买|收到|收货|到货|货到|到手|签收", t)
        and not re.search(r"退|换|退款|质量|坏|破损|保修|运费|规则|政策|投诉|人工|推荐|选购|想买|购买前|不想买", t)
        and not requests_human(t)
    )


def requires_kb(text: str) -> bool:
    """Explicit service-policy questions need evidence even if a model ignores tools."""
    t = (text or "").strip()
    if requests_human(t) or asks_assistant_identity(t):
        return False
    if needs_after_sale_clarification(t):
        return True
    topic = re.search(r"退货|退换|退款|保修|售后|运费|三包|发票|开票|配送|送货|人工客服", t)
    if not topic:
        return False
    if re.search(r"规则|政策|条件|标准|期限|规定|流程|要求", t):
        return True
    if re.search(r"(?:^|[，。；！？,;!?\s])(?:帮我|我要|我想|请)(?:申请|发起|提交|办|办理)?(?:退款|退货|售后)", t):
        return False
    return bool(re.search(r"几天|多久|谁|怎么|如何|能否|是否|支持|几点|上班|[?？吗]", t))
