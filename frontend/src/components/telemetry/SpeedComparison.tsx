import { useRef, useEffect } from 'react';
import * as d3 from 'd3';
import type { DriverTelemetry, SpeedComparisonPoint } from '../../types';

interface Props {
  drivers: DriverTelemetry[];
  comparison: SpeedComparisonPoint[];
}

export default function SpeedComparison({ drivers, comparison }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || comparison.length === 0 || drivers.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = 900;
    const height = 400;
    const margin = { top: 30, right: 30, bottom: 50, left: 60 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const xScale = d3.scaleLinear()
      .domain(d3.extent(comparison, (d) => d.distance) as [number, number])
      .range([0, innerW]);

    const allSpeeds = comparison.flatMap((d) => Object.values(d.speeds));
    const yScale = d3.scaleLinear()
      .domain([d3.min(allSpeeds)! - 10, d3.max(allSpeeds)! + 10])
      .range([innerH, 0]);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    const tooltip = d3.select(tooltipRef.current);

    // Grid
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(10).tickSize(-innerH).tickFormat(() => ''))
      .call((g) => { g.selectAll('line').attr('stroke', '#333'); g.select('.domain').remove(); });

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickSize(-innerW).tickFormat(() => ''))
      .call((g) => { g.selectAll('line').attr('stroke', '#333'); g.select('.domain').remove(); });

    // Area fill between two drivers
    const driverCodes = drivers.map((d) => d.driver);
    if (driverCodes.length === 2) {
      const [d1, d2] = driverCodes;
      const area = d3.area<SpeedComparisonPoint>()
        .x((d) => xScale(d.distance))
        .y0((d) => yScale(d.speeds[d1] ?? 0))
        .y1((d) => yScale(d.speeds[d2] ?? 0))
        .curve(d3.curveMonotoneX);

      g.append('path')
        .datum(comparison)
        .attr('d', area)
        .attr('fill', 'rgba(0, 255, 0, 0.12)')
        .attr('stroke', 'none');
    }

    // Speed lines
    drivers.forEach((driver) => {
      const line = d3.line<SpeedComparisonPoint>()
        .x((d) => xScale(d.distance))
        .y((d) => yScale(d.speeds[driver.driver] ?? 0))
        .curve(d3.curveMonotoneX);

      g.append('path')
        .datum(comparison)
        .attr('d', line)
        .attr('fill', 'none')
        .attr('stroke', driver.color)
        .attr('stroke-width', 2.5);
    });

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(10))
      .call((g) => { g.selectAll('text').attr('fill', '#aaa').style('font-size', '11px'); g.select('.domain').attr('stroke', '#444'); });

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8))
      .call((g) => { g.selectAll('text').attr('fill', '#aaa').style('font-size', '11px'); g.select('.domain').attr('stroke', '#444'); });

    // Axis labels
    svg.append('text')
      .attr('x', margin.left + innerW / 2).attr('y', height - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa').style('font-size', '12px')
      .text('Track Distance (m)');

    svg.append('text')
      .attr('transform', `translate(16, ${margin.top + innerH / 2}) rotate(-90)`)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa').style('font-size', '12px')
      .text('Speed (km/h)');

    // Crosshair tooltip
    const bisector = d3.bisector<SpeedComparisonPoint, number>((d) => d.distance).left;

    const crosshairLine = g.append('line')
      .attr('y1', 0).attr('y2', innerH)
      .attr('stroke', '#666').attr('stroke-width', 1)
      .attr('stroke-dasharray', '4,4')
      .style('opacity', 0);

    g.append('rect')
      .attr('width', innerW).attr('height', innerH)
      .attr('fill', 'none')
      .attr('pointer-events', 'all')
      .on('mousemove', (event: MouseEvent) => {
        const [mx] = d3.pointer(event);
        const distance = xScale.invert(mx);
        const idx = bisector(comparison, distance, 1);
        const d0 = comparison[idx - 1];
        const d1 = comparison[idx];
        if (!d0) return;
        const d = d1 && distance - d0.distance > d1.distance - distance ? d1 : d0;

        crosshairLine
          .attr('x1', xScale(d.distance)).attr('x2', xScale(d.distance))
          .style('opacity', 1);

        const lines = drivers.map((drv) => {
          const speed = d.speeds[drv.driver];
          return `<span style="color:${drv.color}">${drv.driver}: ${speed?.toFixed(1) ?? '—'} km/h</span>`;
        });

        tooltip
          .style('opacity', '1')
          .style('left', `${event.offsetX + 12}px`)
          .style('top', `${event.offsetY - 20}px`)
          .html(`<div class="text-gray-400 mb-1">${d.distance.toFixed(0)}m</div>${lines.join('<br/>')}`);
      })
      .on('mouseout', () => {
        crosshairLine.style('opacity', 0);
        tooltip.style('opacity', '0');
      });

    // Legend
    const legendG = svg.append('g').attr('transform', `translate(${margin.left}, ${margin.top - 5})`);
    drivers.forEach((driver, i) => {
      const x = i * 180;
      legendG.append('line')
        .attr('x1', x).attr('y1', 5).attr('x2', x + 20).attr('y2', 5)
        .attr('stroke', driver.color).attr('stroke-width', 2.5);
      legendG.append('text')
        .attr('x', x + 26).attr('y', 9)
        .attr('fill', '#ccc').style('font-size', '12px')
        .text(`${driver.driver} - ${driver.lap_time}`);
    });

  }, [drivers, comparison]);

  return (
    <div className="bg-surface-700 rounded-lg p-4 mb-6 relative">
      <h3 className="text-base font-display font-bold mb-3 text-gray-200">Speed Comparison Along Track</h3>
      <div className="relative">
        <svg ref={svgRef} className="w-full" style={{ maxHeight: '400px' }} />
        <div
          ref={tooltipRef}
          className="absolute pointer-events-none bg-surface-600 text-white text-xs px-2 py-1 rounded opacity-0 transition-opacity font-mono"
          style={{ zIndex: 10 }}
        />
      </div>
    </div>
  );
}
