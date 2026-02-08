import { useRef, useEffect } from 'react';
import * as d3 from 'd3';
import type { DegradationResponse } from '../../types';
import { COMPOUND_COLORS } from '../../constants/f1';

interface Props {
  degradation: DegradationResponse;
}

export default function DegradationChart({ degradation }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const { compounds, models } = degradation;
    const compoundNames = Object.keys(compounds);
    if (compoundNames.length === 0) return;

    const width = 900;
    const height = 400;
    const margin = { top: 30, right: 30, bottom: 50, left: 70 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const allLife = compoundNames.flatMap((c) => compounds[c].tyre_life);
    const allTime = compoundNames.flatMap((c) => compounds[c].avg_lap_time);

    const xScale = d3.scaleLinear()
      .domain([d3.min(allLife)! - 1, d3.max(allLife)! + 1])
      .range([0, innerW]);
    const yScale = d3.scaleLinear()
      .domain([d3.min(allTime)! - 0.5, d3.max(allTime)! + 0.5])
      .range([innerH, 0]);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Grid
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickSize(-innerW).tickFormat(() => ''))
      .call((g) => { g.selectAll('line').attr('stroke', '#333'); g.select('.domain').remove(); });
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(10).tickSize(-innerH).tickFormat(() => ''))
      .call((g) => { g.selectAll('line').attr('stroke', '#333'); g.select('.domain').remove(); });

    const line = d3.line<{ x: number; y: number }>()
      .x((d) => xScale(d.x))
      .y((d) => yScale(d.y));

    compoundNames.forEach((compound) => {
      const data = compounds[compound];
      const color = COMPOUND_COLORS[compound] || '#888';
      const model = models[compound];

      const points = data.tyre_life.map((tl, i) => ({ x: tl, y: data.avg_lap_time[i] }));

      g.append('path')
        .datum(points)
        .attr('d', line)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 2.5);

      g.selectAll(null)
        .data(points)
        .join('circle')
        .attr('cx', (d) => xScale(d.x))
        .attr('cy', (d) => yScale(d.y))
        .attr('r', 4)
        .attr('fill', color)
        .attr('stroke', compound === 'HARD' ? '#333' : 'none')
        .attr('stroke-width', 1);

      if (model) {
        const xMin = d3.min(data.tyre_life)!;
        const xMax = d3.max(data.tyre_life)!;
        const trendPoints = d3.range(xMin, xMax + 0.5, (xMax - xMin) / 50).map((x) => ({
          x,
          y: model.base_time + model.deg_rate * x,
        }));

        g.append('path')
          .datum(trendPoints)
          .attr('d', line)
          .attr('fill', 'none')
          .attr('stroke', color)
          .attr('stroke-width', 1)
          .attr('stroke-dasharray', '6,4')
          .attr('opacity', 0.6);
      }
    });

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(10))
      .call((g) => { g.selectAll('text').attr('fill', '#aaa').style('font-size', '11px'); g.select('.domain').attr('stroke', '#444'); });
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickFormat((d) => `${Number(d).toFixed(1)}`))
      .call((g) => { g.selectAll('text').attr('fill', '#aaa').style('font-size', '11px'); g.select('.domain').attr('stroke', '#444'); });

    // Labels
    svg.append('text')
      .attr('x', margin.left + innerW / 2).attr('y', height - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa').style('font-size', '12px')
      .text('Tyre Life (laps)');
    svg.append('text')
      .attr('transform', `translate(16, ${margin.top + innerH / 2}) rotate(-90)`)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa').style('font-size', '12px')
      .text('Lap Time (seconds)');

    // Legend
    const legendG = svg.append('g').attr('transform', `translate(${margin.left + innerW - 250}, ${margin.top + 10})`);
    compoundNames.forEach((compound, i) => {
      const color = COMPOUND_COLORS[compound] || '#888';
      const y = i * 22;
      legendG.append('rect')
        .attr('x', 0).attr('y', y).attr('width', 14).attr('height', 14)
        .attr('fill', color).attr('rx', 2)
        .attr('stroke', compound === 'HARD' ? '#555' : 'none');
      legendG.append('text')
        .attr('x', 20).attr('y', y + 11)
        .attr('fill', '#ccc').style('font-size', '12px')
        .text(compound);
    });

  }, [degradation]);

  return (
    <div className="bg-surface-700 rounded-lg p-4 mb-6">
      <h3 className="text-base font-display font-bold mb-3 text-gray-200">Tire Degradation Curves</h3>
      <svg ref={svgRef} className="w-full" style={{ maxHeight: '400px' }} />
    </div>
  );
}
