'use client';

import { RecipeStep } from '@/lib/types';
import { useMemo, useState } from 'react';

interface GanttChartProps {
  steps: RecipeStep[];
}

const STEP_TYPE_COLORS: Record<RecipeStep['type'], string> = {
  prep: '#3B82F6',
  cook: '#F97316',
  finish: '#10B981',
};

const STEP_TYPE_LABELS: Record<RecipeStep['type'], string> = {
  prep: 'Prep',
  cook: 'Cooking',
  finish: 'Finishing',
};

const ROW_MULTIPLIER = 5; // fifths of a minute (reduced for more compact display)
const MIN_ROW_HEIGHT = 2; // px per fifth (reduced for mobile optimization)
const MIN_TIMELINE_HEIGHT = 400; // Reduced minimum height for mobile

export default function GanttChart({ steps }: GanttChartProps) {
  const [selectedStep, setSelectedStep] = useState<RecipeStep | null>(null);
  const [orientation, setOrientation] = useState<'horizontal' | 'vertical'>('vertical');

  if (!steps || steps.length === 0) {
    return (
      <div className="gantt-empty">
        No timeline data available
      </div>
    );
  }

  const maxTime = Math.max(...steps.map(s => s.end_min), 0);
  const safeMaxTime = Math.max(maxTime, 1);

  const timeMarks = useMemo(() => {
    const marks: number[] = [];
    const interval = safeMaxTime > 40 ? 10 : 5;
    for (let i = 0; i <= safeMaxTime; i += interval) {
      marks.push(i);
    }
    if (marks[marks.length - 1] !== safeMaxTime) {
      marks.push(safeMaxTime);
    }
    return marks;
  }, [safeMaxTime]);

  const totalRows = Math.ceil(safeMaxTime * ROW_MULTIPLIER);
  const rowHeight = Math.max(MIN_ROW_HEIGHT, MIN_TIMELINE_HEIGHT / totalRows);
  const verticalHeight = totalRows * rowHeight;
  const gridTemplateRows = `repeat(${totalRows}, ${rowHeight}px)`;

  const handleStepClick = (step: RecipeStep) => {
    setSelectedStep(step);
  };

  const renderHorizontalChart = () => (
    <div className="gantt-horizontal">
      <div className="gantt-axis gantt-axis-horizontal">
        {timeMarks.map(mark => (
          <div
            key={mark}
            className="gantt-axis-mark"
            style={{ left: `${(mark / safeMaxTime) * 100}%` }}
          >
            <span>{mark} min</span>
          </div>
        ))}
      </div>

      <div className="gantt-rows">
        {steps.map(step => {
          const leftPercent = (step.start_min / safeMaxTime) * 100;
          const widthPercent = Math.max(
            ((step.end_min - step.start_min) / safeMaxTime) * 100,
            0.5
          );

          return (
            <div
              key={step.id}
              className={`gantt-row ${selectedStep?.id === step.id ? 'selected' : ''}`}
              onClick={() => handleStepClick(step)}
            >
              <div className="gantt-row-info">
                <div>
                  <p className="gantt-row-label">{step.label}</p>
                  <p className="gantt-row-meta">
                    {STEP_TYPE_LABELS[step.type]} • {step.duration_min} min • Start {step.start_min}m
                  </p>
                </div>
                <span className={`gantt-step-type ${step.type}`}>
                  {STEP_TYPE_LABELS[step.type]}
                </span>
              </div>
              <div className="gantt-row-track">
                <div
                  className="gantt-step-bar"
                  style={{
                    left: `${leftPercent}%`,
                    width: `${widthPercent}%`,
                    backgroundColor: STEP_TYPE_COLORS[step.type],
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderVerticalChart = () => (
    <div className="gantt-vertical">
      <div className="gantt-timeline-vertical" style={{ height: verticalHeight }}>
        <div className="gantt-axis-vertical" style={{ height: verticalHeight }}>
          {timeMarks.map(mark => (
            <div
              key={mark}
              className="gantt-axis-mark-vertical"
              style={{ top: `${(mark / safeMaxTime) * 100}%` }}
            >
              <span>{mark}m</span>
            </div>
          ))}
          <div className="gantt-axis-label">Minutes</div>
        </div>

        <div
          className="gantt-steps-vertical"
          style={{ gridTemplateRows, height: verticalHeight }}
        >
          {steps.map(step => {
            const startIndex = Math.min(
              Math.floor(step.start_min * ROW_MULTIPLIER),
              totalRows - 1
            );
            const endIndex = Math.max(
              startIndex + 1,
              Math.ceil(step.end_min * ROW_MULTIPLIER)
            );
            const rowStart = startIndex + 1;
            const rowEnd = Math.min(endIndex + 1, totalRows + 1);

            return (
              <div
                key={step.id}
                className={`gantt-step-vertical ${selectedStep?.id === step.id ? 'selected' : ''}`}
                style={{ gridRow: `${rowStart} / ${rowEnd}` }}
                onClick={() => handleStepClick(step)}
              >
                <div
                  className="gantt-step-bar-vertical"
                  style={{ backgroundColor: STEP_TYPE_COLORS[step.type] }}
                >
                  <div className="gantt-step-label-vertical">
                    <span>{step.label}</span>
                    <span className="gantt-step-duration-vertical">
                      {step.duration_min} min • {step.start_min}–{step.end_min} min
                    </span>
                  </div>
                  <span className={`gantt-step-type contrast ${step.type}`}>
                    {STEP_TYPE_LABELS[step.type]}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );

  return (
    <div className={`gantt-chart ${orientation}`}>
      <div className="gantt-controls">
        <div className="gantt-runtime">
          Timeline length <strong>{safeMaxTime} min</strong>
        </div>
        <button
          onClick={() =>
            setOrientation(prev => (prev === 'vertical' ? 'horizontal' : 'vertical'))
          }
          className="gantt-toggle-btn"
        >
          Switch to {orientation === 'vertical' ? 'Horizontal' : 'Vertical'}
        </button>
      </div>

      {orientation === 'vertical' ? renderVerticalChart() : renderHorizontalChart()}

      {selectedStep && (
        <div className="gantt-details">
          <div className="gantt-details-header">
            <h3>{selectedStep.label}</h3>
            <span className={`gantt-step-type ${selectedStep.type}`}>
              {STEP_TYPE_LABELS[selectedStep.type]}
            </span>
          </div>
          <div className="gantt-details-grid">
            <div>
              <strong>Duration</strong>
              <span>{selectedStep.duration_min} minutes</span>
            </div>
            <div>
              <strong>Timing</strong>
              <span>{selectedStep.start_min}–{selectedStep.end_min} min</span>
            </div>
            {selectedStep.temperature_c && (
              <div>
                <strong>Temperature</strong>
                <span>{selectedStep.temperature_c}°C</span>
              </div>
            )}
            {selectedStep.equipment.length > 0 && (
              <div>
                <strong>Equipment</strong>
                <span>{selectedStep.equipment.join(', ')}</span>
              </div>
            )}
            {selectedStep.requires.length > 0 && (
              <div>
                <strong>Requires</strong>
                <span>{selectedStep.requires.join(', ')}</span>
              </div>
            )}
            {selectedStep.can_overlap_with.length > 0 && (
              <div>
                <strong>Can overlap with</strong>
                <span>{selectedStep.can_overlap_with.join(', ')}</span>
              </div>
            )}
          </div>
          <div className="gantt-details-text">
            {selectedStep.raw_text}
          </div>
          {selectedStep.notes && (
            <div className="gantt-details-text note">
              {selectedStep.notes}
            </div>
          )}
          <button
            onClick={() => setSelectedStep(null)}
            className="gantt-close-btn"
          >
            Clear selection
          </button>
        </div>
      )}
    </div>
  );
}
