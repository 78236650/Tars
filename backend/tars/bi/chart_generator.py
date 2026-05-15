"""图表生成器：基于查询结果生成 ECharts option"""
import json
from typing import Dict, Any, List, Optional


class ChartGenerator:
    """根据查询结果生成 ECharts 图表配置"""

    SUPPORTED_TYPES = {"line", "bar", "pie", "scatter", "table"}

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider

    def generate(
        self,
        data: List[Dict[str, Any]],
        columns: List[str],
        user_question: str = "",
        chart_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成图表配置
        返回: {
            "chart_type": "line|bar|pie|scatter|table",
            "title": "...",
            "echarts_option": {...},
            "data_summary": "...",
            "raw_data": [...]
        }
        """
        if not data:
            return {
                "chart_type": "table",
                "title": "查询结果",
                "echarts_option": {},
                "data_summary": "无数据",
                "raw_data": [],
            }

        # 自动推断图表类型
        inferred_type = chart_type or self._infer_chart_type(data, columns)
        if inferred_type not in self.SUPPORTED_TYPES:
            inferred_type = "table"

        # 生成 ECharts option
        if inferred_type == "table":
            echarts_option = self._build_table_option(data, columns)
        elif inferred_type == "pie":
            echarts_option = self._build_pie_option(data, columns)
        elif inferred_type == "line":
            echarts_option = self._build_line_option(data, columns)
        elif inferred_type == "bar":
            echarts_option = self._build_bar_option(data, columns)
        elif inferred_type == "scatter":
            echarts_option = self._build_scatter_option(data, columns)
        else:
            echarts_option = self._build_table_option(data, columns)

        summary = self._generate_summary(data, columns, inferred_type)

        return {
            "chart_type": inferred_type,
            "title": user_question or "数据图表",
            "echarts_option": echarts_option,
            "data_summary": summary,
            "raw_data": data,
        }

    def _infer_chart_type(self, data: List[Dict], columns: List[str]) -> str:
        """根据数据特征推断最合适的图表类型"""
        if len(data) <= 1:
            return "table"

        # 检查数值列数量
        numeric_cols = []
        categorical_cols = []
        for col in columns:
            if not data:
                continue
            val = data[0].get(col)
            if isinstance(val, (int, float)):
                numeric_cols.append(col)
            else:
                categorical_cols.append(col)

        row_count = len(data)

        # 只有一列数值 + 一列分类 → pie
        if len(numeric_cols) == 1 and len(categorical_cols) == 1 and row_count <= 10:
            return "pie"

        # 有时间/日期列 + 数值 → line
        if len(numeric_cols) >= 1 and row_count > 5:
            for col in categorical_cols:
                if any(kw in col.lower() for kw in ["date", "time", "day", "month", "year", "dt"]):
                    return "line"

        # 少量分类 → bar
        if len(numeric_cols) >= 1 and row_count <= 20:
            return "bar"

        # 两列数值 → scatter
        if len(numeric_cols) == 2 and len(categorical_cols) == 0:
            return "scatter"

        return "table"

    def _build_table_option(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        return {
            "type": "table",
            "columns": [{"field": col, "header": col} for col in columns],
            "data": data,
        }

    def _build_pie_option(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        name_col = None
        value_col = None
        for col in columns:
            if value_col is None and isinstance(data[0].get(col), (int, float)):
                value_col = col
            elif name_col is None:
                name_col = col

        if not name_col or not value_col:
            return self._build_table_option(data, columns)

        pie_data = []
        for row in data:
            name = str(row.get(name_col, ""))
            val = row.get(value_col, 0)
            if val is not None:
                pie_data.append({"name": name, "value": val})

        return {
            "tooltip": {"trigger": "item"},
            "legend": {"top": "5%", "left": "center"},
            "series": [
                {
                    "type": "pie",
                    "radius": ["40%", "70%"],
                    "avoidLabelOverlap": False,
                    "itemStyle": {"borderRadius": 10, "borderColor": "#fff", "borderWidth": 2},
                    "label": {"show": False, "position": "center"},
                    "emphasis": {
                        "label": {"show": True, "fontSize": 20, "fontWeight": "bold"}
                    },
                    "labelLine": {"show": False},
                    "data": pie_data,
                }
            ],
        }

    def _build_line_option(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        x_col = None
        y_cols = []
        for col in columns:
            if x_col is None and not isinstance(data[0].get(col), (int, float)):
                x_col = col
            elif isinstance(data[0].get(col), (int, float)):
                y_cols.append(col)

        if not x_col:
            x_col = columns[0]
        if not y_cols:
            return self._build_table_option(data, columns)

        x_data = [str(row.get(x_col, "")) for row in data]
        series = []
        for y_col in y_cols:
            series_data = []
            for row in data:
                val = row.get(y_col)
                series_data.append(val if val is not None else 0)
            series.append({
                "name": y_col,
                "type": "line",
                "data": series_data,
                "smooth": True,
            })

        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": y_cols},
            "xAxis": {"type": "category", "data": x_data, "boundaryGap": False},
            "yAxis": {"type": "value"},
            "series": series,
        }

    def _build_bar_option(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        x_col = None
        y_cols = []
        for col in columns:
            if x_col is None and not isinstance(data[0].get(col), (int, float)):
                x_col = col
            elif isinstance(data[0].get(col), (int, float)):
                y_cols.append(col)

        if not x_col:
            x_col = columns[0]
        if not y_cols:
            return self._build_table_option(data, columns)

        x_data = [str(row.get(x_col, "")) for row in data]
        series = []
        for y_col in y_cols:
            series_data = []
            for row in data:
                val = row.get(y_col)
                series_data.append(val if val is not None else 0)
            series.append({
                "name": y_col,
                "type": "bar",
                "data": series_data,
            })

        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": y_cols},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": {"type": "value"},
            "series": series,
        }

    def _build_scatter_option(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        numeric_cols = [col for col in columns if isinstance(data[0].get(col), (int, float))]
        if len(numeric_cols) < 2:
            return self._build_table_option(data, columns)

        x_col, y_col = numeric_cols[0], numeric_cols[1]
        series_data = []
        for row in data:
            x_val = row.get(x_col)
            y_val = row.get(y_col)
            if x_val is not None and y_val is not None:
                series_data.append([x_val, y_val])

        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "value", "name": x_col, "scale": True},
            "yAxis": {"type": "value", "name": y_col, "scale": True},
            "series": [
                {
                    "type": "scatter",
                    "data": series_data,
                    "symbolSize": 10,
                }
            ],
        }

    def _generate_summary(self, data: List[Dict], columns: List[str], chart_type: str) -> str:
        """生成数据摘要"""
        if not data:
            return "无数据"

        row_count = len(data)
        numeric_cols = []
        for col in columns:
            if isinstance(data[0].get(col), (int, float)):
                numeric_cols.append(col)

        if not numeric_cols:
            return f"共 {row_count} 条记录"

        summaries = []
        for col in numeric_cols:
            values = [row.get(col) for row in data if row.get(col) is not None]
            if not values:
                continue
            total = sum(values)
            avg = total / len(values)
            max_val = max(values)
            min_val = min(values)
            summaries.append(f"{col}: 总计 {total:.2f}, 平均 {avg:.2f}, 最大 {max_val}, 最小 {min_val}")

        return f"共 {row_count} 条记录。" + "；".join(summaries)

    async def generate_with_llm(
        self,
        data: List[Dict[str, Any]],
        columns: List[str],
        user_question: str = "",
    ) -> Dict[str, Any]:
        """使用 LLM 生成图表配置（更智能的推荐）"""
        if self.llm_provider is None or len(data) == 0:
            return self.generate(data, columns, user_question)

        sample_data = json.dumps(data[:5], ensure_ascii=False, default=str)
        prompt = f"""你是一位数据可视化专家。根据以下查询结果，推荐最合适的图表类型并生成 ECharts 配置。

用户问题：{user_question}

数据列：{columns}

样例数据（前5行）：
{sample_data}

请返回 JSON 格式：
{{
    "chart_type": "line|bar|pie|scatter|table",
    "title": "图表标题",
    "echarts_option": {{...}},
    "data_summary": "数据总结"
}}

注意：echarts_option 必须是有效的 ECharts 配置对象。"""

        try:
            from ..channels.base import ChannelMessage
            msg = ChannelMessage(role="user", content=prompt)
            response = await self.llm_provider.complete([msg])
            content = response.content if hasattr(response, "content") else str(response)

            json_str = content.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            result = json.loads(json_str.strip())
            result["raw_data"] = data
            return result
        except Exception:
            return self.generate(data, columns, user_question)
