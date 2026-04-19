"""
情报来源可信度验证器
对不同来源的情报进行可信度评分，过滤低质量个人观点
"""
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from utils.logger import get_logger

logger = get_logger('source_validator')


class SourceType(Enum):
    """来源类型枚举"""
    OFFICIAL = "official"           # 官方公告/财报
    INSTITUTION = "institution"     # 机构研报
    MAINSTREAM_MEDIA = "mainstream" # 主流财经媒体
    INDUSTRY_MEDIA = "industry"     # 行业媒体
    SELF_MEDIA = "self_media"       # 自媒体/个人博客
    SOCIAL_MEDIA = "social"         # 社交媒体/股吧
    UNKNOWN = "unknown"             # 未知来源


class CredibilityLevel(Enum):
    """可信度等级"""
    HIGH = "high"           # 高可信度 (0.8-1.0)
    MEDIUM_HIGH = "medium_high"  # 中高可信度 (0.6-0.8)
    MEDIUM = "medium"       # 中等可信度 (0.4-0.6)
    LOW = "low"             # 低可信度 (0.2-0.4)
    VERY_LOW = "very_low"   # 极低可信度 (0.0-0.2)


@dataclass
class SourceCredibility:
    """来源可信度评估结果"""
    source_type: SourceType
    credibility_level: CredibilityLevel
    credibility_score: float      # 0.0-1.0
    is_institutional: bool        # 是否机构观点
    bias_warning: List[str]       # 偏见警告
    confidence_adjustment: float  # 建议的置信度调整系数


class SourceValidator:
    """情报来源验证器"""
    
    # 官方来源域名
    OFFICIAL_DOMAINS = [
        'cninfo.com.cn',      # 巨潮资讯
        'sse.com.cn',         # 上交所
        'szse.cn',            # 深交所
        'csrc.gov.cn',        # 证监会
        'samr.gov.cn',        # 市场监管总局
        'gov.cn',             # 政府网站
    ]
    
    # 主流财经媒体域名
    MAINSTREAM_DOMAINS = [
        'finance.sina.com.cn',
        'eastmoney.com',
        '10jqka.com.cn',
        'hexun.com',
        'cs.com.cn',          # 中证网
        'stcn.com',           # 证券时报网
        '21jingji.com',       # 21世纪经济报道
        'caixin.com',         # 财新
        'yicai.com',          # 第一财经
        'jrj.com.cn',         # 金融界
        'ccstock.com',        # 经济参考报
    ]
    
    # 机构研报来源特征
    INSTITUTION_PATTERNS = [
        r'证券研报',
        r'券商研报',
        r'研究报告',
        r'投资评级',
        r'目标价.*元',
        r'给予.*评级',
        r'维持.*评级',
        r'上调.*评级',
        r'下调.*评级',
        r'盈利预测',
    ]
    
    # 个人/自媒体平台域名
    SELF_MEDIA_DOMAINS = [
        'toutiao.com',        # 今日头条
        'baijiahao.baidu',    # 百家号
        'weibo.com',          # 微博
        'mp.weixin.qq.com',   # 微信公众号
        'xueqiu.com',         # 雪球
        'zhihu.com',          # 知乎
        'jianshu.com',        # 简书
    ]
    
    # 社交媒体/股吧域名
    SOCIAL_DOMAINS = [
        'guba.eastmoney.com', # 东方财富股吧
        'guba.sina.com.cn',   # 新浪股吧
        'xueqiu.com',         # 雪球
    ]
    
    # 情绪化词汇（个人观点特征）
    EMOTIONAL_KEYWORDS = [
        '暴涨', '暴跌', '起飞', '跳水',
        '十倍', '百倍', '千倍', '万倍',
        '碾压', '吊打', '秒杀', '绝杀',
        '惊天', '史诗级', '历史级', '核弹级',
        '必涨', '必跌', '稳赚', '暴富',
        '剑指', '直指', '冲击',
        '赶紧', '马上', '立刻', '紧急',
        '重磅', '突发', '震惊', '吓人',
        '牛股', '妖股', '黑马', '龙头',
        '强烈推荐', '重点推荐', '独家解析',
    ]
    
    # 可信度评分配置
    CREDIBILITY_SCORES = {
        SourceType.OFFICIAL: 0.95,
        SourceType.INSTITUTION: 0.80,
        SourceType.MAINSTREAM_MEDIA: 0.65,
        SourceType.INDUSTRY_MEDIA: 0.55,
        SourceType.SELF_MEDIA: 0.25,
        SourceType.SOCIAL_MEDIA: 0.15,
        SourceType.UNKNOWN: 0.30,
    }
    
    def __init__(self):
        self.logger = logger
    
    def validate_source(self, url: str, title: str, 
                        content: str = "") -> SourceCredibility:
        """
        验证情报来源可信度
        
        Args:
            url: 来源URL
            title: 文章标题
            content: 文章内容（可选）
            
        Returns:
            SourceCredibility 可信度评估结果
        """
        # 1. 识别来源类型
        source_type = self._identify_source_type(url, title, content)
        
        # 2. 计算基础可信度
        base_score = self.CREDIBILITY_SCORES[source_type]
        
        # 3. 检测偏见和情绪化内容
        bias_warnings = self._detect_bias(title, content)
        
        # 4. 根据偏见调整可信度
        adjusted_score = self._adjust_for_bias(base_score, bias_warnings)
        
        # 5. 判断是否机构观点
        is_institutional = self._check_institutional(title, content, url)
        
        # 6. 计算置信度调整系数
        confidence_adj = self._calculate_confidence_adjustment(
            source_type, adjusted_score, bias_warnings
        )
        
        # 7. 确定可信度等级
        credibility_level = self._get_credibility_level(adjusted_score)
        
        return SourceCredibility(
            source_type=source_type,
            credibility_level=credibility_level,
            credibility_score=adjusted_score,
            is_institutional=is_institutional,
            bias_warning=bias_warnings,
            confidence_adjustment=confidence_adj
        )
    
    def _identify_source_type(self, url: str, title: str, 
                               content: str) -> SourceType:
        """识别来源类型"""
        url_lower = url.lower() if url else ""
        
        # 检查官方来源
        for domain in self.OFFICIAL_DOMAINS:
            if domain in url_lower:
                return SourceType.OFFICIAL
        
        # 检查社交媒体
        for domain in self.SOCIAL_DOMAINS:
            if domain in url_lower:
                return SourceType.SOCIAL_MEDIA
        
        # 检查自媒体平台
        for domain in self.SELF_MEDIA_DOMAINS:
            if domain in url_lower:
                # 如果是股吧文章，可能是用户生成内容
                if 'guba' in url_lower or '财富号' in title or '股吧' in title:
                    return SourceType.SOCIAL_MEDIA
                return SourceType.SELF_MEDIA
        
        # 检查主流财经媒体
        for domain in self.MAINSTREAM_DOMAINS:
            if domain in url_lower:
                # 需要进一步判断是媒体原创还是用户投稿
                if self._is_user_generated(url, title, content):
                    return SourceType.SELF_MEDIA
                return SourceType.MAINSTREAM_MEDIA
        
        # 检查是否包含机构研报特征
        if self._has_institution_features(title, content):
            return SourceType.INSTITUTION
        
        return SourceType.UNKNOWN
    
    def _is_user_generated(self, url: str, title: str, content: str) -> bool:
        """判断是否用户生成内容"""
        # 东方财富财富号
        if 'caifuhao.eastmoney.com' in url.lower():
            return True
        
        # 标题包含个人观点特征
        personal_patterns = [
            r'我看多',
            r'我看空',
            r'我的观点',
            r'个人观点',
            r'股友\d+',
        ]
        for pattern in personal_patterns:
            if re.search(pattern, title):
                return True
        
        return False
    
    def _has_institution_features(self, title: str, content: str) -> bool:
        """检查是否包含机构研报特征"""
        text = f"{title} {content}"
        for pattern in self.INSTITUTION_PATTERNS:
            if re.search(pattern, text):
                return True
        return False
    
    def _detect_bias(self, title: str, content: str) -> List[str]:
        """检测偏见和情绪化内容"""
        warnings = []
        text = f"{title} {content}"
        
        detected_keywords = []
        for keyword in self.EMOTIONAL_KEYWORDS:
            if keyword in text:
                detected_keywords.append(keyword)
        
        if detected_keywords:
            warnings.append(f"情绪化词汇: {', '.join(detected_keywords[:5])}")
        
        # 检测极端数字
        extreme_numbers = re.findall(r'[十百千万]倍', text)
        if extreme_numbers:
            warnings.append(f"极端预期: {', '.join(extreme_numbers[:3])}")
        
        # 检测绝对化表述
        absolute_patterns = [
            (r'必[涨跌]', '绝对化预测'),
            (r'稳赚', '收益承诺'),
            (r'确定性.*?100%', '过度确定'),
        ]
        for pattern, warning in absolute_patterns:
            if re.search(pattern, text):
                warnings.append(warning)
        
        return warnings
    
    def _adjust_for_bias(self, base_score: float, 
                         bias_warnings: List[str]) -> float:
        """根据偏见调整可信度"""
        if not bias_warnings:
            return base_score
        
        # 每个偏见警告扣减一定分数
        penalty = len(bias_warnings) * 0.1
        
        # 情绪化词汇特别处理
        for warning in bias_warnings:
            if '情绪化词汇' in warning:
                penalty += 0.15
            if '极端预期' in warning:
                penalty += 0.20
        
        adjusted = max(0.1, base_score - penalty)
        return round(adjusted, 2)
    
    def _check_institutional(self, title: str, content: str, url: str) -> bool:
        """检查是否机构观点"""
        # 机构名称特征
        institution_patterns = [
            r'[\u4e00-\u9fa5]{2,4}证券',
            r'[\u4e00-\u9fa5]{2,4}证券研究所',
            r'[\u4e00-\u9fa5]{2,4}资管',
            r'[\u4e00-\u9fa5]{2,4}基金',
            r'券商研报',
            r'机构研报',
        ]
        
        text = f"{title} {content}"
        for pattern in institution_patterns:
            if re.search(pattern, text):
                return True
        
        return False
    
    def _calculate_confidence_adjustment(self, source_type: SourceType,
                                         credibility_score: float,
                                         bias_warnings: List[str]) -> float:
        """计算建议的置信度调整系数"""
        # 基础调整系数
        base_adj = credibility_score
        
        # 社交媒体和自媒体需要额外降低
        if source_type in [SourceType.SOCIAL_MEDIA, SourceType.SELF_MEDIA]:
            base_adj *= 0.5
        
        # 有偏见警告的额外降低
        if bias_warnings:
            base_adj *= 0.7
        
        return round(base_adj, 2)
    
    def _get_credibility_level(self, score: float) -> CredibilityLevel:
        """根据分数确定可信度等级"""
        if score >= 0.8:
            return CredibilityLevel.HIGH
        elif score >= 0.6:
            return CredibilityLevel.MEDIUM_HIGH
        elif score >= 0.4:
            return CredibilityLevel.MEDIUM
        elif score >= 0.2:
            return CredibilityLevel.LOW
        else:
            return CredibilityLevel.VERY_LOW
    
    def validate_intelligence_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证并标注情报项
        
        Args:
            item: 情报项字典，包含 title, summary, url 等
            
        Returns:
            添加了可信度标注的情报项
        """
        url = item.get('url', '')
        title = item.get('title', '')
        content = item.get('summary', '')
        
        credibility = self.validate_source(url, title, content)
        
        # 添加可信度信息
        validated_item = item.copy()
        validated_item['credibility'] = {
            'source_type': credibility.source_type.value,
            'level': credibility.credibility_level.value,
            'score': credibility.credibility_score,
            'is_institutional': credibility.is_institutional,
            'bias_warnings': credibility.bias_warning,
            'confidence_adjustment': credibility.confidence_adjustment,
        }
        
        # 如果是低可信度来源，添加警告标签
        if credibility.credibility_level in [CredibilityLevel.LOW, CredibilityLevel.VERY_LOW]:
            validated_item['warning'] = f"⚠️ 低可信度来源({credibility.source_type.value})"
            if credibility.bias_warning:
                validated_item['warning'] += f" - {', '.join(credibility.bias_warning)}"
        
        return validated_item
    
    def filter_low_credibility(self, items: List[Dict[str, Any]], 
                               min_score: float = 0.3) -> Tuple[List[Dict], List[Dict]]:
        """
        过滤低可信度情报
        
        Args:
            items: 情报列表
            min_score: 最低可信度分数阈值
            
        Returns:
            (可信情报列表, 过滤掉的情报列表)
        """
        validated_items = []
        filtered_items = []
        
        for item in items:
            validated = self.validate_intelligence_item(item)
            score = validated['credibility']['score']
            
            if score >= min_score:
                validated_items.append(validated)
            else:
                filtered_items.append(validated)
        
        if filtered_items:
            self.logger.info(
                f"过滤低可信度情报 {len(filtered_items)} 条 "
                f"(阈值: {min_score})"
            )
        
        return validated_items, filtered_items


# 全局实例
source_validator = SourceValidator()
