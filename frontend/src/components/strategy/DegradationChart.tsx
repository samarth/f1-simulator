import { useRef, useEffect } from 'react';
import * as d3 from 'd3';
import type { DegradationResponse } from '../../types';
import { COMPOUND_COLORS } from '../../constants/f1';

interface Props {
  degradation: DegradationResponse;
  maxLaps?: number; // Optional: extend x-axis to this many laps (e.g., race length)
}

export default function DegradationChart({ degradation, maxLaps = 50 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const { compounds, models } = degradation;
    const compoundNames = Object.keys(compounds);
    if (compoundNames.length === 0) return;

    // Dynamic width based on container
    const containerWidth = containerRef.current.clientWidth;
    const width = Math.max(900, containerWidth - 32); // min 900, or container width minus padding
    const height = 420;
    const margin = { top: 30, right: 120, bottom: 50, left: 70 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    svg.attr('viewBox', `0 0 ${width} ${height}`);
    svg.attr('width', width);
    svg.attr('height', height);

    const allLife = compoundNames.flatMap((c) => compounds[c].tyre_life);
    const allTime = compoundNames.flatMap((c) => compounds[c].avg_lap_time);
    const dataMaxLife = d3.max(allLife)!;

    // Extend x-axis to maxLaps or at least 10 beyond data
    const xMax = Math.max(maxLaps, dataMaxLife + 10);
    
    // Calculate y range including extrapolated values
    let yMin = d3.min(allTime)!;
    let yMax = d3.max(allTime)!;
    
    // Check extrapolated values to set y scale
    compoundNames.forEach((compound) => {
      const model = models[compound];
      if (model) {
        const extrapolatedY = model.base_time + model.deg_rate * xMax;
        yMax = Math.max(yMax, extrapolatedY);
      }
    });

    const xScale = d3.scaleLinear()
      .domain([0, xMax])
      .range([0, innerW]);
    const yScale = d3.scaleLinear()
      .domain([yMin - 0.5, yMax + 0.5])
      .range([innerH, 0]);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Grid
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickSize(-innerW).tickFormat(() => ''))
      .call((g) => { g.selectAll('line').attr('stroke', '#333'); g.select('.domain').remove(); });
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(Math.min(20, xMax / 5)).tickSize(-innerH).tickFormat(() => ''))
      .call((g) => { g.selectAll('line').attr('stroke', '#333'); g.select('.domain').remove(); });

    // Add shaded region for "extrapolated" zone
    if (dataMaxLife < xMax) {
      g.append('rect')
        .attr('x', xScale(dataMaxLife))
        .attr('y', 0)
        .attr('width', xScale(xMax) - xScale(dataMaxLife))
        .attr('height', innerH)
        .attr('fill', '#1a1a2e')
        .attr('opacity', 0.5);
      
      g.append('text')
        .attr('x', xScale(dataMaxLife) + 10)
        .attr('y', 20)
        .attr('fill', '#666')
        .style('font-size', '11px')
        .text('Extrapolated →');
    }

    const line = d3.line<{ x: number; y: number }>()
      .x((d) => xScale(d.x))
      .y((d) => yScale(d.y));

    compoundNames.forEach((compound) => {
      const data = compounds[compound];
      const color = COMPOUND_COLORS[compound] || '#888';
      const model = models[compound];

      const points = data.tyre_life.map((tl, i) => ({ x: tl, y: data.avg_lap_time[i] }));

      // Actual data line
      g.append('path')
        .datum(points)
        .attr('d', line)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 2.5);

      // Data points
      g.selectAll(null)
        .data(points)
        .join('circle')
        .attr('cx', (d) => xScale(d.x))
        .attr('cy', (d) => yScale(d.y))
        .attr('r', 4)
        .attr('fill', color)
        .attr('stroke', compound === 'HARD' ? '#333' : 'none')
        .attr('stroke-width', 1);

      // Extended trendline (extrapolated)
      if (model) {
        const xMin = 1;
        const trendPoints = d3.range(xMin, xMax + 0.5, 1).map((x) => ({
          x,
          y: model.base_time + model.deg_rate * x,
        }));

        g.append('path')
          .datum(trendPoints)
          .attr('d', line)
          .attr('fill', 'none')
          .attr('stroke', color)
          .attr('stroke-width', 1.5)
          .attr('stroke-dasharray', '6,4')
          .attr('opacity', 0.6);
      }
    });

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(Math.min(20, xMax / 5)))
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

    // Legend (moved to right side)
    const legendG = svg.append('g').attr('transform', `translate(${margin.left + innerW + 15}, ${margin.top + 10})`);
    compoundNames.forEach((compound, i) => {
      const color = COMPOUND_COLORS[compound] || '#888';
      const model = models[compound];
      const y = i * 50;
      
      legendG.append('rect')
        .attr('x', 0).attr('y', y).attr('width', 14).attr('height', 14)
        .attr('fill', color).attr('rx', 2)
        .attr('stroke', compound === 'HARD' ? '#555' : 'none');
      legendG.append('text')
        .attr('x', 20).attr('y', y + 11)
        .attr('fill', '#ccc').style('font-size', '12px').style('font-weight', 'bold')
        .text(compound);
      
      if (model) {
        legendG.append('text')
          .attr('x', 0).attr('y', y + 28)
          .attr('fill', '#888').style('font-size', '10px')
          .text(`+${(model.deg_rate * 1000).toFixed(0)}ms/lap`);
      }
    });

  }, [degradation, maxLaps]);

  return (
    <div ref={containerRef} className="bg-surface-700 rounded-lg p-4 mb-6">
      <h3 className="text-base font-display font-bold mb-3 text-gray-200">
        Tire Degradation Curves
        <span className="text-sm font-normal text-gray-500 ml-2">
          (dashed lines show predicted degradation)
        </span>
      </h3>
      <div className="overflow-x-auto">
        <svg ref={svgRef} style={{ minWidth: '900px' }} />
      </div>
    </div>
  );
}
