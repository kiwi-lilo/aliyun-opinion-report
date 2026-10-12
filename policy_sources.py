"""Approved policy information sources.

The list is deliberately explicit: discovery may use only these domains and
the fetcher never treats a search result page as a reportable source.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicySource:
    name: str
    region: str
    source_type: str
    index_url: str
    allowed_domains: tuple[str, ...]
    section_urls: tuple[str, ...] = ()
    section_keywords: tuple[str, ...] = ("政策", "通知", "文件", "发布", "方案", "办法")


MINISTRIES = (
    ("国家发展改革委", "ndrc.gov.cn"), ("工业和信息化部", "miit.gov.cn"),
    ("人力资源和社会保障部", "mohrss.gov.cn"), ("国家金融监督管理总局", "nfra.gov.cn"),
    ("民政部", "mca.gov.cn"), ("住房和城乡建设部", "mohurd.gov.cn"),
    ("市场监管总局", "samr.gov.cn"), ("国家数据局", "nda.gov.cn"),
    ("科技部", "most.gov.cn"), ("生态环境部", "mee.gov.cn"),
    ("农业农村部", "moa.gov.cn"), ("交通运输部", "mot.gov.cn"),
    ("商务部", "mofcom.gov.cn"), ("教育部", "moe.gov.cn"),
    ("国家卫生健康委", "nhc.gov.cn"), ("国家税务总局", "chinatax.gov.cn"),
    ("国家知识产权局", "cnipa.gov.cn"),
)

# Verified栏目入口 discovered from the official sites. Sources without a
# stable栏目 URL continue to use their registered domain as a fallback and
# remain visible as source errors instead of silently producing fake items.
SECTION_URLS = {
    "国家发展改革委": "https://www.ndrc.gov.cn/xxgk/zcfb/tz/",
    "工业和信息化部": "https://www.miit.gov.cn/zwgk/zcwj/index.html",
    "中国政府网": "https://www.gov.cn/zhengce/zuixin/",
    "民政部": "https://www.mca.gov.cn/n152/n165/index.html",
    "生态环境部": "https://www.mee.gov.cn/zcwj/",
    "交通运输部": "https://xxgk.mot.gov.cn/xzgfxwj/",
    "农业农村部": "https://www.moa.gov.cn/gk/zcfg/",
    "商务部": "https://www.mofcom.gov.cn/zcfb/",
    "教育部": "http://www.moe.gov.cn/was5/web/search?channelid=239993",
    "国家数据局": "https://www.nda.gov.cn/sjj/zwgk/zcfb/list/index_pc_1.html",
    "民政部": "https://www.mca.gov.cn/n152/n165/index.html",
    "国家税务总局": "https://fgk.chinatax.gov.cn/zcfgk/c100027/list.html",
    "国家知识产权局": "https://www.cnipa.gov.cn/col/col59/index.html",
    "人力资源和社会保障部": "https://www.mohrss.gov.cn/xxgk2020/fdzdgknr/zcfg/",
    "国家金融监督管理总局": "https://www.nfra.gov.cn/cn/view/pages/ItemList.html?itemId=926&itemName=%E6%94%BF%E7%AD%96%E6%B3%95%E8%A7%84&itemPId=923&itemUrl=ItemListRightMore.html",
    "住房和城乡建设部": "https://www.mohurd.gov.cn/gongkai/zc/wgk/",
    "市场监管总局": "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/",
    "科技部": "https://www.most.gov.cn/xxgk/xinxifenlei/fdzdgknr/fgzc/gfxwj/",
    "国家卫生健康委": "https://www.nhc.gov.cn/wjw/zcfg/list.shtml",
    "上海": "https://www.shanghai.gov.cn/nw12344/index.html",
    "广州": "https://www.gz.gov.cn/zwgk/zcjd/",
    "杭州": "https://www.hangzhou.gov.cn/col/col1229063400/index.html",
    "武汉": "https://www.wuhan.gov.cn/zwgk/xxgk/",
    "西安": "https://www.xa.gov.cn/gk/zcwj/",
    "成都": "https://www.chengdu.gov.cn/chengdu/c123886/zfxxgk.shtml",
    "南京": "https://www.nanjing.gov.cn/xxgk/",
    "银川": "https://www.yinchuan.gov.cn/zwgk/zcwj/",
}

PROVINCES = {
    "北京": "beijing.gov.cn", "上海": "shanghai.gov.cn", "江苏": "jiangsu.gov.cn",
    "浙江": "zj.gov.cn", "广东": "gd.gov.cn", "湖南": "hunan.gov.cn", "湖北": "hubei.gov.cn",
    "山东": "shandong.gov.cn", "天津": "tj.gov.cn", "四川": "sc.gov.cn", "重庆": "cq.gov.cn",
    "河南": "henan.gov.cn", "安徽": "ah.gov.cn", "福建": "fujian.gov.cn", "河北": "hebei.gov.cn",
}

PROVINCE_SECTION_URLS = {
    "北京": "https://www.beijing.gov.cn/zhengce/zhengcefagui/",
    "上海": "https://www.shanghai.gov.cn/nw12344/index.html",
    "江苏": "http://www.jiangsu.gov.cn/col/col84242/index.html",
    "浙江": "https://www.zj.gov.cn/col/col1544911/index.html",
    "广东": "https://www.gd.gov.cn/zwgk/wjk/index.html",
    "山东": "http://gb.shandong.gov.cn/col/col310952/index.html",
    "天津": "https://www.tj.gov.cn/zwgk/szfwj/",
    "四川": "https://www.sc.gov.cn/10462/wza2012/zwxx/zwxx.shtml",
    "重庆": "https://www.cq.gov.cn/zwgk/zfxxgkml/szfwj/xzgfxwj/szf/",
    "河南": "https://www.henan.gov.cn/zwgk/zcjd/",
    "安徽": "https://www.ah.gov.cn/public/column/1681?type=4&catId=6708431&action=list",
    "福建": "https://www.fujian.gov.cn/zwgk/zxwj/",
    "河北": "https://www.hebei.gov.cn/columns/49f13cc2-db03-4d0c-b4fe-2f3f659d3b6e/index.html",
    "湖北": "https://www.hubei.gov.cn/zwgk/",
    "湖南": "https://www.hunan.gov.cn/hnszf/xxgk/wjk/szfwj/wjk_glrb.html",
}

CAPITALS = {
    "广州": "gz.gov.cn", "南京": "nanjing.gov.cn", "杭州": "hangzhou.gov.cn",
    "长沙": "changsha.gov.cn", "武汉": "wuhan.gov.cn", "济南": "jinan.gov.cn",
    "成都": "chengdu.gov.cn", "郑州": "zhengzhou.gov.cn", "合肥": "hefei.gov.cn",
    "福州": "fuzhou.gov.cn", "石家庄": "sjz.gov.cn", "沈阳": "shenyang.gov.cn",
    "长春": "changchun.gov.cn", "哈尔滨": "harbin.gov.cn", "南昌": "nanchang.gov.cn",
    "昆明": "kunming.gov.cn", "贵阳": "guiyang.gov.cn", "西宁": "xining.gov.cn",
    "兰州": "lanzhou.gov.cn", "银川": "yinchuan.gov.cn", "乌鲁木齐": "urumqi.gov.cn",
    "呼和浩特": "hlbe.gov.cn", "海口": "haikou.gov.cn", "太原": "taiyuan.gov.cn",
    "西安": "xa.gov.cn",
}

# Verified, explicitly bounded city-level public information/policy portals.
# Avoid bare .gov.cn roots: many resolve inconsistently or are not the current
# official portal. Add cities here only with a known policy/government section.
PREFECTURE_CITIES = {
    "苏州": ("www.suzhou.gov.cn", "https://www.suzhou.gov.cn/szsrmzf/xxgk/zcwj.shtml"),
    "宁波": ("www.ningbo.gov.cn", "https://www.ningbo.gov.cn/col/col1229099760/index.html"),
    "温州": ("www.wenzhou.gov.cn", "https://www.wenzhou.gov.cn/col/col1229116944/index.html"),
    "无锡": ("www.wuxi.gov.cn", "https://www.wuxi.gov.cn/zwgk/zcwj/index.shtml"),
    "佛山": ("www.foshan.gov.cn", "https://www.foshan.gov.cn/zwgk/zfgb/"),
    "东莞": ("www.dg.gov.cn", "https://www.dg.gov.cn/zwgk/zfgb/"),
    "珠海": ("www.zhuhai.gov.cn", "https://www.zhuhai.gov.cn/zwgk/zcwj/"),
    "惠州": ("www.huizhou.gov.cn", "https://www.huizhou.gov.cn/zwgk/zcwj/"),
    "襄阳": ("www.xiangyang.gov.cn", "https://www.xiangyang.gov.cn/zwgk/zcwj/"),
    "宜昌": ("www.yichang.gov.cn", "https://www.yichang.gov.cn/col/col6402/index.html"),
    "烟台": ("www.yantai.gov.cn", "https://www.yantai.gov.cn/col/col11778/index.html"),
    "潍坊": ("www.weifang.gov.cn", "https://www.weifang.gov.cn/xxgk/"),
    "洛阳": ("www.ly.gov.cn", "https://www.ly.gov.cn/zwgk/zcwj/"),
    "芜湖": ("www.wuhu.gov.cn", "https://www.wuhu.gov.cn/openness/PolicyContent/showList/"),
    "泉州": ("www.quanzhou.gov.cn", "https://www.quanzhou.gov.cn/zfb/xxgk/zfxxgkzl/"),
    "唐山": ("www.tangshan.gov.cn", "https://www.tangshan.gov.cn/zhengwugongkai/"),
    "保定": ("www.baoding.gov.cn", "https://www.baoding.gov.cn/zwgk/"),
}


def _source(name: str, region: str, domain: str, source_type: str = "部委官网") -> PolicySource:
    # Domain root remains a discovery fallback. Site-specific栏目 URLs can be
    # added here without changing the fetcher contract.
    return PolicySource(name, region, source_type, f"https://{domain}/", (domain,), ())


def _with_section(source: PolicySource) -> PolicySource:
    url = SECTION_URLS.get(source.name) or PROVINCE_SECTION_URLS.get(source.name)
    return PolicySource(source.name, source.region, source.source_type, url or source.index_url,
                        source.allowed_domains, (url,) if url else ())


CITY_SOURCES = tuple(
    PolicySource(name, "地级市", "市政府官网", url, (host,))
    for name, (host, url) in PREFECTURE_CITIES.items()
)

POLICY_SOURCES = tuple(_with_section(_source(name, "国家部委", domain)) for name, domain in MINISTRIES) + tuple(
    _with_section(_source(name, "外省", domain, "政府官网")) for name, domain in PROVINCES.items()
) + tuple(_with_section(_source(name, "省会城市", domain, "市政府官网")) for name, domain in CAPITALS.items()) + CITY_SOURCES + (
    _with_section(PolicySource("中国政府网", "中央", "权威媒体", "https://www.gov.cn/", ("gov.cn",))),
    PolicySource("人民网地方频道", "媒体地方版块", "权威媒体", "https://local.people.com.cn/", ("people.com.cn",)),
    PolicySource("新华网地方频道", "媒体地方版块", "权威媒体", "https://www.news.cn/local/", ("news.cn",)),
    PolicySource("中国新闻网地方频道", "媒体地方版块", "权威媒体", "https://www.chinanews.com.cn/地方/", ("chinanews.com.cn",)),
    PolicySource("央视网地方版块", "媒体地方版块", "权威媒体", "https://news.cctv.com/", ("cctv.com",)),
    PolicySource("光明网地方版块", "媒体地方版块", "权威媒体", "https://politics.gmw.cn/", ("gmw.cn",)),
)


def source_for_url(url: str) -> PolicySource | None:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for source in POLICY_SOURCES:
        if any(host == domain or host.endswith("." + domain) for domain in source.allowed_domains):
            return source
    return None
