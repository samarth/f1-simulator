import { useRef, useEffect } from 'react';
import * as d3 from 'd3';
import type { SimulateResponse, StintInput } from '../../types';
import { COMPOUND_COLORS } from '../../constants/f1';

interface Props {
  simulation: SimulateResponse;
  stints: StintInput[];
  driver: string;
}

export default function LapTimeChart({ simulation, stints, driver }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const { simulated_laps, actual } = simulation;

    const width = 900;
    const height = 450;
    const margin = { top: 30, right: 30, bottom: 50, left: 70 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const allTimes = simulated_laps.map((l) => l.time_sec);
    if (actual?.lap_times) {
      allTimes.push(...actual.lap_times.map((l) => l.time_sec));
    }

    const xScale = d3.scaleLinear()
      .domain([1, d3.max(simulated_laps, (d) => d.lap)!])
      .range([0, innerW]);
    const yScale = d3.scaleLinear()
      .domain([d3.min(allTimes)! - 1, d3.max(allTimes)! + 1])
      .range([innerH, 0]);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Grid
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickSize(-innerW).tickFormat(() => ''))
      .call((g) => { g.selectAll('line').attr('stroke', '#333'); g.select('.domain').remove(); });

    // Compound background bands
    let stintStart = 1;
    stints.forEach((stint) => {
      const laps = Number(stint.laps) || 0;
      if (laps <= 0) return;
      const color = COMPOUND_COLORS[stint.compound] || '#888';
      g.append('rect')
        .attr('x', xScale(stintStart - 0.5))
        .attr('y', 0)
        .attr('width', xScale(stintStart + laps - 0.5) - xScale(stintStart - 0.5))
        .attr('height', innerH)
        .attr('fill', color)
        .attr('opacity', 0.06);
      stintStart += laps;
    });

    const lineFn = d3.line<{ lap: number; time_sec: number }>()
      .x((d) => xScale(d.lap))
      .y((d) => yScale(d.time_sec));

    // User strategy line
    g.append('path')
      .datum(simulated_laps)
      .attr('d', lineFn)
      .attr('fill', 'none')
      .attr('stroke', '#00BFFF')
      .attr('stroke-width', 2.5);

    // Actual strategy line
    if (actual?.lap_times && actual.lap_times.length > 0) {
      g.append('path')
        .datum(actual.lap_times)
        .attr('d', lineFn)
        .attr('fill', 'none')
        .attr('stroke', '#FF6B6B')
        .attr('stroke-width', 2.5);
    }

    // Pit stop vlines - user
    simulated_laps
      .filter((l) => l.is_pit_lap)
      .forEach((l) => {
        g.append('line')
          .attr('x1', xScale(l.lap)).attr('x2', xScale(l.lap))
          .attr('y1', 0).attr('y2', innerH)
          .attr('stroke', '#00BFFF')
          .attr('stroke-width', 1)
          .attr('stroke-dasharray', '6,4')
          .attr('opacity', 0.5);
      });

    // Pit stop vlines - actual
    if (actual?.pit_laps) {
      actual.pit_laps.forEach((p) => {
        g.append('line')
          .attr('x1', xScale(p.lap)).attr('x2', xScale(p.lap))
          .attr('y1', 0).attr('y2', innerH)
          .attr('stroke', '#FF6B6B')
          .attr('stroke-width', 1)
          .attr('stroke-dasharray', '6,4')
          .attr('opacity', 0.5);
      });
    }

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(15))
      .call((g) => { g.selectAll('text').attr('fill', '#aaa').style('font-size', '11px'); g.select('.domain').attr('stroke', '#444'); });
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickFormat((d) => `${Number(d).toFixed(1)}`))
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
      .text('Lap Time (seconds)');

    // Legend
    const legendG = svg.append('g').attr('transform', `translate(${margin.left}, ${margin.top - 10})`);
    [
      { label: 'Your Strategy', color: '#00BFFF' },
      { label: `${driver} Actual`, color: '#FF6B6B' },
    ].forEach((item, i) => {
      const x = i * 180;
      legendG.append('line')
        .attr('x1', x).attr('y1', 5).attr('x2', x + 20).attr('y2', 5)
        .attr('stroke', item.color).attr('stroke-width', 2.5);
      legendG.append('text')
        .attr('x', x + 26).attr('y', 9)
        .attr('fill', '#ccc').style('font-size', '12px')
        .text(item.label);
    });

  }, [simulation, stints, driver]);

  return (
    <div className="bg-surface-700 rounded-lg p-4">
      <h3 className="text-base font-display font-bold mb-1 text-gray-200">
        Lap Time Comparison
      </h3>
      <p className="text-xs text-gray-500 mb-3">
        Each lap's time — lower is faster. Dashed lines show pit stops. Background colors show your tire compounds.
      </p>
      <svg ref={svgRef} className="w-full" style={{ maxHeight: '450px' }} />
    </div>
  );
}
