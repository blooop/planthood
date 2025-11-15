'use client';

import { RecipeStep } from '@/lib/types';
import { useState } from 'react';

interface GanttChartProps {
  steps: RecipeStep[];
}

const STEP_TYPE_COLORS = {
  prep: '#3B82F6',    // Blue
  cook: '#F97316',    // Orange
  finish: '#10B981',  // Green
};

export default function GanttChart({ steps }: GanttChartProps) {
  const [selectedStep, setSelectedStep] = useState<RecipeStep | null>(null);
  const [orientation, setOrientation] = useState<'horizontal' | 'vertical'>('horizontal');

  if (!steps || steps.length === 0) {
    return (
      <div className="gantt-empty">
        No timeline data available
      </div>
    );
  }

  const maxTime = Math.max(...steps.map(s => s.end_min), 0);
  const timeMarks: number[] = [];
  const markInterval = 5;
  for (let i = 0; i <= maxTime; i += markInterval) {
    timeMarks.push(i);
  }

  const renderHorizontalChart = () => (
    <div className="gantt-chart horizontal">
      <div className="gantt-controls">
        <button
          onClick={() => setOrientation('vertical')}
          className="gantt-toggle-btn"
        >
          Switch to Vertical
        </button>
      </div>

      <div className="gantt-timeline">
        {/* Time axis */}
        <div className="gantt-axis">
          {timeMarks.map(mark => (
            <div
              key={mark}
              className="gantt-axis-mark"
              style={{ left: `${(mark / maxTime) * 100}%` }}
            >
              <span>{mark} min</span>
            </div>
          ))}
        </div>

        {/* Steps */}
        <div className="gantt-steps">
          {steps.map(step => {
            const leftPercent = (step.start_min / maxTime) * 100;
            const widthPercent = (step.duration_min / maxTime) * 100;

            return (
              <div
                key={step.id}
                className={`gantt-step ${selectedStep?.id === step.id ? 'selected' : ''}`}
                onClick={() => setSelectedStep(step)}
              >
                <div className="gantt-step-label">
                  {step.label}
                </div>
                <div
                  className="gantt-step-bar"
                  style={{
                    left: `${leftPercent}%`,
                    width: `${widthPercent}%`,
                    backgroundColor: STEP_TYPE_COLORS[step.type],
                  }}
                >
                  <span className="gantt-step-duration">
                    {step.duration_min} MIN
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Step details */}
      {selectedStep && (
        <div className="gantt-details">
          <h3>{selectedStep.label}</h3>
          <div className="gantt-details-grid">
            <div>
              <strong>Type:</strong> {selectedStep.type}
            </div>
            <div>
              <strong>Duration:</strong> {selectedStep.duration_min} minutes
            </div>
            <div>
              <strong>Time:</strong> {selectedStep.start_min}–{selectedStep.end_min} min
            </div>
            {selectedStep.equipment.length > 0 && (
              <div>
                <strong>Equipment:</strong> {selectedStep.equipment.join(', ')}
              </div>
            )}
            {selectedStep.temperature_c && (
              <div>
                <strong>Temperature:</strong> {selectedStep.temperature_c}°C
              </div>
            )}
            {selectedStep.requires.length > 0 && (
              <div>
                <strong>Requires:</strong> {selectedStep.requires.join(', ')}
              </div>
            )}
            {selectedStep.can_overlap_with.length > 0 && (
              <div>
                <strong>Can overlap with:</strong> {selectedStep.can_overlap_with.join(', ')}
              </div>
            )}
            {selectedStep.notes && (
              <div>
                <strong>Notes:</strong> {selectedStep.notes}
              </div>
            )}
          </div>
          <div className="gantt-details-text">
            {selectedStep.raw_text}
          </div>
          <button
            onClick={() => setSelectedStep(null)}
            className="gantt-close-btn"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );

  const renderVerticalChart = () => (
    <div className="gantt-chart vertical">
      <div className="gantt-controls">
        <button
          onClick={() => setOrientation('horizontal')}
          className="gantt-toggle-btn"
        >
          Switch to Horizontal
        </button>
      </div>

      <div className="gantt-timeline-vertical">
        {/* Time axis */}
        <div className="gantt-axis-vertical">
          {timeMarks.map(mark => (
            <div
              key={mark}
              className="gantt-axis-mark-vertical"
              style={{ top: `${(mark / maxTime) * 100}%` }}
            >
              <span>{mark}</span>
            </div>
          ))}
          <div className="gantt-axis-label">Minutes</div>
        </div>

        {/* Steps */}
        <div className="gantt-steps-vertical">
          {steps.map(step => {
            const topPercent = (step.start_min / maxTime) * 100;
            const heightPercent = (step.duration_min / maxTime) * 100;

            return (
              <div
                key={step.id}
                className={`gantt-step-vertical ${selectedStep?.id === step.id ? 'selected' : ''}`}
                onClick={() => setSelectedStep(step)}
              >
                <div
                  className="gantt-step-bar-vertical"
                  style={{
                    top: `${topPercent}%`,
                    height: `${heightPercent}%`,
                    backgroundColor: STEP_TYPE_COLORS[step.type],
                  }}
                >
                  <span className="gantt-step-label-vertical">
                    {step.label}
                  </span>
                  <span className="gantt-step-duration-vertical">
                    {step.duration_min}m
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Step details */}
      {selectedStep && (
        <div className="gantt-details">
          <h3>{selectedStep.label}</h3>
          <div className="gantt-details-grid">
            <div>
              <strong>Type:</strong> {selectedStep.type}
            </div>
            <div>
              <strong>Duration:</strong> {selectedStep.duration_min} minutes
            </div>
            <div>
              <strong>Time:</strong> {selectedStep.start_min}–{selectedStep.end_min} min
            </div>
            {selectedStep.equipment.length > 0 && (
              <div>
                <strong>Equipment:</strong> {selectedStep.equipment.join(', ')}
              </div>
            )}
          </div>
          <div className="gantt-details-text">
            {selectedStep.raw_text}
          </div>
          <button
            onClick={() => setSelectedStep(null)}
            className="gantt-close-btn"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );

  return orientation === 'horizontal' ? renderHorizontalChart() : renderVerticalChart();
}
