import { useRef, useEffect } from 'react';
import * as d3 from 'd3';
import type { DriverTelemetry } from '../../types';

interface Props {
  drivers: DriverTelemetry[];
}

export default function TrackMap({ drivers }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || drivers.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = 800;
    const height = 600;
    const margin = { top: 20, right: 40, bottom: 40, left: 20 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const allX = drivers.flatMap((d) => d.track.map((p) => p.x));
    const allY = drivers.flatMap((d) => d.track.map((p) => p.y));
    const allSpeed = drivers.flatMap((d) => d.track.map((p) => p.speed));

    const xExtent = d3.extent(allX) as [number, number];
    const yExtent = d3.extent(allY) as [number, number];

    const dataW = xExtent[1] - xExtent[0];
    const dataH = yExtent[1] - yExtent[0];
    const dataAspect = dataW / dataH;
    const viewAspect = innerW / innerH;

    let scaleX: d3.ScaleLinear<number, number>;
    let scaleY: d3.ScaleLinear<number, number>;

    if (dataAspect > viewAspect) {
      scaleX = d3.scaleLinear().domain(xExtent).range([margin.left, margin.left + innerW]);
      const scaledH = innerW / dataAspect;
      const offset = (innerH - scaledH) / 2;
      scaleY = d3.scaleLinear().domain(yExtent).range([margin.top + offset + scaledH, margin.top + offset]);
    } else {
      scaleY = d3.scaleLinear().domain(yExtent).range([margin.top + innerH, margin.top]);
      const scaledW = innerH * dataAspect;
      const offset = (innerW - scaledW) / 2;
      scaleX = d3.scaleLinear().domain(xExtent).range([margin.left + offset, margin.left + offset + scaledW]);
    }

    const colorScale = d3.scaleSequential(d3.interpolateViridis)
      .domain(d3.extent(allSpeed) as [number, number]);

    const g = svg.append('g');
    const tooltip = d3.select(tooltipRef.current);

    const primary = drivers[0];
    g.selectAll('circle.track')
      .data(primary.track)
      .join('circle')
      .attr('class', 'track')
      .attr('cx', (d) => scaleX(d.x))
      .attr('cy', (d) => scaleY(d.y))
      .attr('r', 3)
      .attr('fill', (d) => colorScale(d.speed))
      .attr('opacity', 0.8)
      .on('mouseover', (event, d) => {
        tooltip
          .style('opacity', '1')
          .style('left', `${event.offsetX + 12}px`)
          .style('top', `${event.offsetY - 28}px`)
          .html(`<strong>${primary.driver}</strong><br/>Speed: ${d.speed.toFixed(1)} km/h`);
      })
      .on('mouseout', () => {
        tooltip.style('opacity', '0');
      });

    drivers.slice(1).forEach((driver) => {
      g.selectAll(null)
        .data(driver.track)
        .join('circle')
        .attr('cx', (d) => scaleX(d.x))
        .attr('cy', (d) => scaleY(d.y))
        .attr('r', 2)
        .attr('fill', driver.color)
        .attr('opacity', 0.4);
    });

    // Colorbar
    const defs = svg.append('defs');
    const gradientId = 'speed-gradient';
    const gradient = defs.append('linearGradient')
      .attr('id', gradientId)
      .attr('x1', '0%').attr('y1', '100%')
      .attr('x2', '0%').attr('y2', '0%');

    const speedExtent = d3.extent(allSpeed) as [number, number];
    for (let i = 0; i <= 10; i++) {
      const t = i / 10;
      gradient.append('stop')
        .attr('offset', `${t * 100}%`)
        .attr('stop-color', colorScale(speedExtent[0] + t * (speedExtent[1] - speedExtent[0])));
    }

    const barX = width - 30;
    const barY = margin.top + 40;
    const barH = 200;

    svg.append('rect')
      .attr('x', barX).attr('y', barY)
      .attr('width', 14).attr('height', barH)
      .attr('fill', `url(#${gradientId})`)
      .attr('rx', 2);

    const barScale = d3.scaleLinear().domain(speedExtent).range([barY + barH, barY]);
    const barAxis = d3.axisRight(barScale).ticks(5);
    svg.append('g')
      .attr('transform', `translate(${barX + 14}, 0)`)
      .call(barAxis)
      .call((g) => g.select('.domain').remove())
      .selectAll('text')
      .attr('fill', '#aaa')
      .style('font-size', '10px');

    svg.append('text')
      .attr('x', barX + 7).attr('y', barY - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', '#aaa').style('font-size', '10px')
      .text('km/h');

    // Legend
    const legendY = height - 20;
    drivers.forEach((driver, i) => {
      const x = margin.left + i * 160;
      svg.append('rect')
        .attr('x', x).attr('y', legendY - 10)
        .attr('width', 12).attr('height', 12)
        .attr('fill', i === 0 ? '#77dd77' : driver.color)
        .attr('rx', 2);
      svg.append('text')
        .attr('x', x + 18).attr('y', legendY)
        .attr('fill', '#ccc').style('font-size', '12px').style('font-family', 'Inter, sans-serif')
        .text(`${driver.driver} - ${driver.lap_time}`);
    });

  }, [drivers]);

  return (
    <div className="bg-surface-700 rounded-lg p-4 mb-6 relative">
      <h3 className="text-base font-display font-bold mb-3 text-gray-200">Track Map &mdash; Fastest Laps</h3>
      <div className="relative">
        <svg ref={svgRef} className="w-full" style={{ maxHeight: '600px' }} />
        <div
          ref={tooltipRef}
          className="absolute pointer-events-none bg-surface-600 text-white text-xs px-2 py-1 rounded opacity-0 transition-opacity font-mono"
        />
      </div>
    </div>
  );
}
