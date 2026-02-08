import { useRef, useEffect } from 'react';
import * as d3 from 'd3';
import type { SimulateResponse } from '../../types';

interface Props {
  simulation: SimulateResponse;
  driver: string;
}

export default function CumulativeGapChart({ simulation, driver }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || simulation.cumulative_gap.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const data = simulation.cumulative_gap;

    const width = 900;
    const height = 350;
    const margin = { top: 30, right: 30, bottom: 50, left: 70 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const xScale = d3.scaleLinear()
      .domain(d3.extent(data, (d) => d.lap) as [number, number])
      .range([0, innerW]);

    const yExtent = d3.extent(data, (d) => d.gap) as [number, number];
    const yPad = Math.max(Math.abs(yExtent[0]), Math.abs(yExtent[1])) * 0.1 + 1;
    const yScale = d3.scaleLinear()
      .domain([Math.min(yExtent[0], 0) - yPad, Math.max(yExtent[1], 0) + yPad])
      .range([innerH, 0]);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Grid
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickSize(-innerW).tickFormat(() => ''))
      .call((g) => { g.selectAll('line').attr('stroke', '#333'); g.select('.domain').remove(); });

    // Zero line
    g.append('line')
      .attr('x1', 0).attr('x2', innerW)
      .attr('y1', yScale(0)).attr('y2', yScale(0))
      .attr('stroke', '#888').attr('stroke-width', 1);

    // Area fill
    const area = d3.area<{ lap: number; gap: number }>()
      .x((d) => xScale(d.lap))
      .y0(yScale(0))
      .y1((d) => yScale(d.gap))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('d', area)
      .attr('fill', 'rgba(255, 215, 0, 0.1)')
      .attr('stroke', 'none');

    // Line
    const line = d3.line<{ lap: number; gap: number }>()
      .x((d) => xScale(d.lap))
      .y((d) => yScale(d.gap))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('d', line)
      .attr('fill', 'none')
      .attr('stroke', '#FFD700')
      .attr('stroke-width', 2.5);

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(15))
      .call((g) => { g.selectAll('text').attr('fill', '#aaa').style('font-size', '11px'); g.select('.domain').attr('stroke', '#444'); });
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickFormat((d) => `${Number(d) > 0 ? '+' : ''}${Number(d).toFixed(1)}`))
      .call((g) => { g.selectAll('text').attr('fill', '#aaa').style('font-size', '11px'); g.select('.domain').attr('stroke', '#444'); });

    // Labels
    svg.append('text')
      .attr('x', margin.left + innerW / 2).attr('y', height - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa').style('font-size', '12px')
      .text('Lap Number');
    svg.append('text')
      .attr('transform', `translate(16, ${margin.top + innerH / 2}) rotate(-90)`)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa').style('font-size', '12px')
      .text('Time Difference (seconds)');

    svg.append('text')
      .attr('x', margin.left + innerW - 5).attr('y', margin.top + 15)
      .attr('text-anchor', 'end')
      .attr('fill', '#888').style('font-size', '11px')
      .text("+ = you're slower");

  }, [simulation, driver]);

  return (
    <div className="bg-surface-700 rounded-lg p-4">
      <h3 className="text-base font-display font-bold mb-3 text-gray-200">
        Cumulative Time Gap vs {driver}
      </h3>
      <svg ref={svgRef} className="w-full" style={{ maxHeight: '350px' }} />
    </div>
  );
}
