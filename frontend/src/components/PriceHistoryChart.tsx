import { useEffect, useRef } from "preact/hooks";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  type GridComponentOption,
  type TooltipComponentOption,
} from "echarts/components";
import { init, use, type ComposeOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { LineSeriesOption } from "echarts/charts";
import { formatShortDate, useI18n } from "../lib/i18n";
import type { PricePoint } from "../types";

type EChartsOption = ComposeOption<
  GridComponentOption | TooltipComponentOption | LineSeriesOption
>;

use([GridComponent, TooltipComponent, LineChart, CanvasRenderer]);

export function PriceHistoryChart(props: { points: PricePoint[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const { locale, t } = useI18n();

  useEffect(() => {
    if (!ref.current) {
      return;
    }
    const chart = init(ref.current);
    const option: EChartsOption = {
      tooltip: { trigger: "axis" },
      grid: { left: 28, right: 20, top: 36, bottom: 26 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: props.points.map((point) => formatShortDate(locale, point.observedAt)),
      },
      yAxis: {
        type: "value",
        splitLine: {
          lineStyle: { color: "rgba(20, 33, 61, 0.08)" },
        },
      },
      series: [
        {
          name: t("chart.listedPrice"),
          type: "line",
          smooth: true,
          data: props.points.map((point) => point.listedPrice),
          lineStyle: { color: "#14213d", width: 3 },
          itemStyle: { color: "#14213d" },
          areaStyle: { color: "rgba(20, 33, 61, 0.08)" },
        },
        {
          name: t("chart.effectivePrice"),
          type: "line",
          smooth: true,
          data: props.points.map((point) => point.effectivePrice),
          lineStyle: { color: "#b84c27", width: 3, type: "dashed" },
          itemStyle: { color: "#b84c27" },
        },
      ],
    };
    chart.setOption(option);

    const resize = () => chart.resize();
    window.addEventListener("resize", resize);

    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [locale, props.points, t]);

  return <div class="h-80 w-full" ref={ref} />;
}
