'use client';

import { RecipeStep } from '@/lib/types';
import { useMemo, useState, useEffect } from 'react';

interface GanttChartProps {
  steps: RecipeStep[];
}

// Using CSS variables for theme-aware colors
const getStepTypeColor = (type: RecipeStep['type']): string => {
  const colorMap: Record<RecipeStep['type'], string> = {
    prep: 'var(--color-gantt-prep)',
    cook: 'var(--color-gantt-cook)',
    finish: 'var(--color-gantt-finish)',
  };
  return colorMap[type] ?? 'var(--color-gantt-prep)'; // Default to prep color
};

const STEP_TYPE_LABELS: Record<RecipeStep['type'], string> = {
  prep: 'Prep',
  cook: 'Cooking',
  finish: 'Finishing',
};

// Responsive constants based on screen size
const MOBILE_BREAKPOINT = 768;
const DESKTOP_CONFIG = {
  ROW_MULTIPLIER: 4,
  PIXELS_PER_MIN: 14,
  MIN_TIMELINE_HEIGHT: 480,
  MAX_TIMELINE_HEIGHT: 1000,
};
const MOBILE_CONFIG = {
  ROW_MULTIPLIER: 4,
  PIXELS_PER_MIN: 9,
  MIN_TIMELINE_HEIGHT: 360,
  MAX_TIMELINE_HEIGHT: 800,
};

const CRITICAL_PATH_PREVIEW_COUNT = 5;

export default function GanttChart({ steps }: GanttChartProps) {
  const [selectedStep, setSelectedStep] = useState<RecipeStep | null>(null);
  const [orientation, setOrientation] = useState<'horizontal' | 'vertical'>('horizontal');
  const [isMobile, setIsMobile] = useState(false);
  const [showCriticalOnly, setShowCriticalOnly] = useState(false);
  const [criticalPathExpanded, setCriticalPathExpanded] = useState(false);

  // Detect screen size on mount and resize
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= MOBILE_BREAKPOINT);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Use responsive configuration
  const config = isMobile ? MOBILE_CONFIG : DESKTOP_CONFIG;
  const ROW_MULTIPLIER = config.ROW_MULTIPLIER;
  const MIN_TIMELINE_HEIGHT = config.MIN_TIMELINE_HEIGHT;
  const MAX_TIMELINE_HEIGHT = config.MAX_TIMELINE_HEIGHT;
  const PIXELS_PER_MIN = config.PIXELS_PER_MIN;

  // Calculate critical path statistics
  const criticalPath = useMemo(() => {
    return steps.filter(s => s.is_critical).sort((a, b) => a.start_min - b.start_min);
  }, [steps]);

  const displaySteps = showCriticalOnly ? criticalPath : steps;

  const maxTime = Math.max(...displaySteps.map(s => s.end_min), 0);
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

  // All hooks are above this line, so the early return below never changes hook order.
  if (!steps || steps.length === 0) {
    return (
      <div className="gantt-empty">
        No timeline data available
      </div>
    );
  }

  // Grid granularity for positioning; the height is clamped so long recipes don't
  // produce thousand-pixel-tall charts (rows can be sub-pixel — they only place bars).
  const totalRows = Math.max(1, Math.ceil(safeMaxTime * ROW_MULTIPLIER));
  const verticalHeight = Math.min(
    MAX_TIMELINE_HEIGHT,
    Math.max(MIN_TIMELINE_HEIGHT, Math.round(safeMaxTime * PIXELS_PER_MIN))
  );
  const rowHeight = verticalHeight / totalRows;
  const gridTemplateRows = `repeat(${totalRows}, ${rowHeight}px)`;

  const handleStepClick = (step: RecipeStep) => {
    setSelectedStep(step);
  };

  // Make a clickable div behave like a button for keyboard users.
  const keyActivate = (step: RecipeStep) => (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleStepClick(step);
    }
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
        {displaySteps.map(step => {
          const leftPercent = (step.start_min / safeMaxTime) * 100;
          const widthPercent = Math.max(
            ((step.end_min - step.start_min) / safeMaxTime) * 100,
            0.5
          );

          return (
            <div
              key={step.id}
              className={`gantt-row ${selectedStep?.id === step.id ? 'selected' : ''} ${step.is_critical ? 'critical' : ''}`}
              role="button"
              tabIndex={0}
              aria-label={`${step.label}, ${STEP_TYPE_LABELS[step.type]}, ${step.duration_min} minutes`}
              onClick={() => handleStepClick(step)}
              onKeyDown={keyActivate(step)}
            >
              <div className="gantt-row-info">
                <div>
                  <p className="gantt-row-label">
                    {step.is_critical && (
                      <span
                        className="critical-indicator"
                        aria-label="Critical step"
                        role="img"
                      >
                        ⚡
                        <span className="sr-only">Critical step</span>
                      </span>
                    )}
                    {step.label}
                  </p>
                  <p className="gantt-row-meta">
                    {STEP_TYPE_LABELS[step.type]} • {step.duration_min} min • Start {step.start_min}m
                    {!step.is_critical && step.slack_min > 0 && (
                      <span className="slack-info"> • {step.slack_min}m slack</span>
                    )}
                  </p>
                </div>
                <span className={`gantt-step-type ${step.type} ${step.is_critical ? 'critical' : ''}`}>
                  {STEP_TYPE_LABELS[step.type]}
                </span>
              </div>
              <div className="gantt-row-track">
                <div
                  className={`gantt-step-bar ${step.is_critical ? 'critical' : ''}`}
                  style={{
                    left: `${leftPercent}%`,
                    width: `${widthPercent}%`,
                    backgroundColor: getStepTypeColor(step.type),
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
          {displaySteps.map(step => {
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
                className={`gantt-step-vertical ${selectedStep?.id === step.id ? 'selected' : ''} ${step.is_critical ? 'critical' : ''}`}
                style={{ gridRow: `${rowStart} / ${rowEnd}` }}
                role="button"
                tabIndex={0}
                aria-label={`${step.label}, ${STEP_TYPE_LABELS[step.type]}, ${step.duration_min} minutes`}
                onClick={() => handleStepClick(step)}
                onKeyDown={keyActivate(step)}
              >
                <div
                  className={`gantt-step-bar-vertical ${step.is_critical ? 'critical' : ''}`}
                  style={{ backgroundColor: getStepTypeColor(step.type) }}
                >
                  <div className="gantt-step-label-vertical">
                    <span>
                      {step.is_critical && (
                        <span
                          className="critical-indicator"
                          aria-label="Critical step"
                          role="img"
                        >
                          ⚡
                          <span className="sr-only">Critical step</span>
                        </span>
                      )}
                      {step.label}
                    </span>
                    <span className="gantt-step-duration-vertical">
                      {step.duration_min} min • {step.start_min}–{step.end_min} min
                      {!step.is_critical && step.slack_min > 0 && ` • ${step.slack_min}m slack`}
                    </span>
                  </div>
                  <span className={`gantt-step-type contrast ${step.type} ${step.is_critical ? 'critical' : ''}`}>
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
      {criticalPath.length > 0 && (
        <div className="gantt-critical-path-summary">
          <h3>⚡ Critical Path ({criticalPath.length} steps)</h3>
          <p className="critical-path-description">
            These steps determine the minimum cooking time. Any delay here delays the entire recipe.
          </p>
          <ol className="critical-path-steps">
            {(criticalPathExpanded ? criticalPath : criticalPath.slice(0, CRITICAL_PATH_PREVIEW_COUNT)).map((step, idx) => (
              <li
                key={step.id}
                role="button"
                tabIndex={0}
                aria-label={`${step.label}, ${step.duration_min} minutes`}
                onClick={() => handleStepClick(step)}
                onKeyDown={keyActivate(step)}
              >
                <span className="step-number">{idx + 1}</span>
                <span className="step-name">{step.label}</span>
                <span className="step-time">{step.duration_min}m</span>
              </li>
            ))}
            {!criticalPathExpanded && criticalPath.length > CRITICAL_PATH_PREVIEW_COUNT && (
              <li className="critical-path-more-steps">
                ...and {criticalPath.length - CRITICAL_PATH_PREVIEW_COUNT} more steps
              </li>
            )}
          </ol>
          {criticalPath.length > CRITICAL_PATH_PREVIEW_COUNT && (
            <button
              className="critical-path-toggle-btn"
              onClick={() => setCriticalPathExpanded(prev => !prev)}
            >
              {criticalPathExpanded ? 'Show less' : 'Show all steps'}
            </button>
          )}
        </div>
      )}

      <div className="gantt-controls">
        <div className="gantt-metadata">
          {safeMaxTime}m total • {criticalPath.length}/{steps.length} critical
          {showCriticalOnly && ' • Showing critical only'}
        </div>
        <div className="gantt-control-buttons">
          <button
            onClick={() => setShowCriticalOnly(!showCriticalOnly)}
            className={`gantt-toggle-btn ${showCriticalOnly ? 'active' : ''}`}
            title="Toggle critical path only"
            aria-label="Toggle critical path only"
            aria-pressed={showCriticalOnly}
          >
            ⚡
          </button>
          <button
            onClick={() =>
              setOrientation(prev => (prev === 'vertical' ? 'horizontal' : 'vertical'))
            }
            className="gantt-toggle-btn"
            title="Toggle orientation"
            aria-label={`Switch to ${orientation === 'vertical' ? 'horizontal' : 'vertical'} layout`}
          >
            ↔↕
          </button>
        </div>
      </div>

      {orientation === 'vertical' ? renderVerticalChart() : renderHorizontalChart()}

      {selectedStep && (
        <div className="gantt-details">
          <div className="gantt-details-header">
            <h3>
              {selectedStep.is_critical && (
                <span
                  className="critical-indicator"
                  aria-label="Critical step"
                  role="img"
                >
                  ⚡
                  <span className="sr-only">Critical step</span>
                </span>
              )}
              {selectedStep.label}
            </h3>
            <span className={`gantt-step-type ${selectedStep.type} ${selectedStep.is_critical ? 'critical' : ''}`}>
              {STEP_TYPE_LABELS[selectedStep.type]}
            </span>
          </div>
          {selectedStep.is_critical && (
            <div className="critical-path-badge">
              <span
                className="critical-path-badge-icon"
                aria-label="Critical path"
                role="img"
              >
                ⚡
                <span className="sr-only">Critical path</span>
              </span>
              On Critical Path - Any delay here delays the entire recipe
            </div>
          )}
          <div className="gantt-details-grid">
            <div>
              <strong>Duration</strong>
              <span>{selectedStep.duration_min} minutes</span>
            </div>
            <div>
              <strong>Timing</strong>
              <span>{selectedStep.start_min}–{selectedStep.end_min} min</span>
            </div>
            {!selectedStep.is_critical && selectedStep.slack_min > 0 && (
              <div>
                <strong>Slack Time</strong>
                <span>{selectedStep.slack_min} min (can be delayed without affecting total time)</span>
              </div>
            )}
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
