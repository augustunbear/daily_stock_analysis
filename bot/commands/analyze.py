# -*- coding: utf-8 -*-
"""
===================================
股票分析命令
===================================

分析指定股票，调用 AI 生成分析报告。
"""

import re
import logging
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse
from market_types import normalize_stock_input, is_isin_code, is_wkn_code

logger = logging.getLogger(__name__)


class AnalyzeCommand(BotCommand):
    """
    股票分析命令
    
    分析指定股票代码，生成 AI 分析报告并推送。
    
    用法：
        /analyze 600519       - 分析贵州茅台
        /analyze 600519 full  - 分析并生成完整报告
    """
    
    @property
    def name(self) -> str:
        return "analyze"
    
    @property
    def aliases(self) -> List[str]:
        return ["a", "分析", "查"]
    
    @property
    def description(self) -> str:
        return "分析指定股票"
    
    @property
    def usage(self) -> str:
        return "/analyze <股票代码|ISIN|WKN> [full]"
    
    def validate_args(self, args: List[str]) -> Optional[str]:
        """验证参数"""
        if not args:
            return "请输入股票代码"
        
        code = args[0].lower()
        
        # 验证股票代码格式
        # A股：6位数字
        # 港股：hk + 5位数字
        # 美股/欧股：字母代码，可带交易所后缀（如 AAPL, SAP.DE）
        # 扩展：支持 ISIN（12位）和 WKN（6位）
        direct_code_ok = (
            re.match(r'^\d{6}$', code) or
            re.match(r'^hk\d{5}$', code) or
            re.match(r'^(?=.*[a-z])[a-z0-9]{1,8}(\.[a-z]{1,5})?$', code)
        )
        if not (direct_code_ok or is_isin_code(code) or is_wkn_code(code)):
            return (
                f"无效的股票代码: {code}"
                "（支持A股6位数字、港股hk+5位、股票代码、ISIN、WKN）"
            )
        
        return None
    
    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """执行分析命令"""
        input_code = args[0].strip()
        code = normalize_stock_input(input_code).lower()

        # ISIN/WKN 解析失败时给出明确提示
        if code == input_code.lower() and (is_isin_code(input_code) or is_wkn_code(input_code)):
            return BotResponse.error_response(
                f"无法将标识符 `{input_code}` 解析为股票代码，请尝试直接输入交易代码（如 `SAP.DE`）"
            )
        
        # 检查是否需要完整报告
        report_type = "full"
        # if len(args) > 1 and args[1].lower() in ["full", "完整", "详细"]:
        #     report_type = "full"
        logger.info(f"[AnalyzeCommand] 分析股票: {input_code} -> {code}, 报告类型: {report_type}")
        
        try:
            # 调用分析服务
            from web.services import get_analysis_service
            from enums import ReportType
            
            service = get_analysis_service()
            
            # 提交异步分析任务
            result = service.submit_analysis(
                code=code,
                report_type=ReportType.from_str(report_type),
                source_message=message
            )
            
            if result.get("success"):
                task_id = result.get("task_id", "")
                return BotResponse.markdown_response(
                    f"✅ **分析任务已提交**\n\n"
                    f"• 输入代码: `{input_code}`\n"
                    f"• 解析代码: `{code}`\n"
                    f"• 报告类型: {ReportType.from_str(report_type).display_name}\n"
                    f"• 任务 ID: `{task_id[:20]}...`\n\n"
                    f"分析完成后将自动推送结果。"
                )
            else:
                error = result.get("error", "未知错误")
                return BotResponse.error_response(f"提交分析任务失败: {error}")
                
        except Exception as e:
            logger.error(f"[AnalyzeCommand] 执行失败: {e}")
            return BotResponse.error_response(f"分析失败: {str(e)[:100]}")
