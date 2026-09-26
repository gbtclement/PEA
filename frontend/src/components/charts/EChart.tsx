import { useEffect, useRef } from "react";
import { LineChart, PieChart, TreemapChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([TreemapChart, PieChart, LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer]);

type Props = {
  option: echarts.EChartsCoreOption;
  className?: string;
  onItemClick?: (data: unknown) => void;
};

export function EChart({ option, className, onItemClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const element = ref.current!;
    const chart = echarts.init(element);
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onItemClick) return;
    const handler = (params: { data?: unknown }) => onItemClick(params.data);
    chart.on("click", handler);
    return () => {
      chart.off("click", handler);
    };
  }, [onItemClick]);

  return <div ref={ref} className={className} />;
}
