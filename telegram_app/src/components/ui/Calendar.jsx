import { useMemo, useState } from "react";
import PropTypes from "prop-types";
import dayjs from "dayjs";
import "./Calendar.css";

/**
 * Calendar — month-grid date picker with range selection and blocked dates.
 *
 * Props:
 *   value: { from: 'YYYY-MM-DD', to: 'YYYY-MM-DD' } | null
 *   onChange: ({from, to}) => void   — both set when user picks a complete range
 *   blockedDates: string[]            — ISO 'YYYY-MM-DD' strings to disable
 *   minDate / maxDate: dayjs|string  — bounds (default: today → +6 months)
 */
export default function Calendar({
  value,
  onChange,
  blockedDates = [],
  minDate,
  maxDate,
}) {
  const today = dayjs().startOf("day");
  const min = dayjs(minDate || today);
  const max = dayjs(maxDate || today.add(6, "month"));
  const [cursor, setCursor] = useState(() =>
    value?.from ? dayjs(value.from).startOf("month") : today.startOf("month"),
  );
  const blockedSet = useMemo(() => new Set(blockedDates), [blockedDates]);

  const monthStart = cursor.startOf("month");
  const monthEnd = cursor.endOf("month");
  const startWeekDay = (monthStart.day() + 6) % 7; // Mon=0
  const daysInMonth = monthEnd.date();
  const cells = [];
  for (let i = 0; i < startWeekDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(monthStart.date(d));

  const from = value?.from ? dayjs(value.from) : null;
  const to = value?.to ? dayjs(value.to) : null;

  const isBlocked = (d) => blockedSet.has(d.format("YYYY-MM-DD"));
  const isOutOfRange = (d) => d.isBefore(min, "day") || d.isAfter(max, "day");
  const inSelected = (d) => from && to && d.isAfter(from, "day") && d.isBefore(to, "day");
  const isFrom = (d) => from && d.isSame(from, "day");
  const isTo = (d) => to && d.isSame(to, "day");

  function handlePick(d) {
    if (isBlocked(d) || isOutOfRange(d)) return;
    if (!from || (from && to)) {
      onChange({ from: d.format("YYYY-MM-DD"), to: null });
      return;
    }
    if (d.isSame(from, "day") || d.isBefore(from, "day")) {
      onChange({ from: d.format("YYYY-MM-DD"), to: null });
      return;
    }
    // Reject ranges crossing a blocked date
    let cur = from.add(1, "day");
    while (cur.isBefore(d, "day")) {
      if (isBlocked(cur)) {
        onChange({ from: d.format("YYYY-MM-DD"), to: null });
        return;
      }
      cur = cur.add(1, "day");
    }
    onChange({ from: from.format("YYYY-MM-DD"), to: d.format("YYYY-MM-DD") });
  }

  const canPrev = monthStart.isAfter(min.startOf("month"));
  const canNext = monthStart.isBefore(max.startOf("month"));

  return (
    <div className="ui-cal">
      <div className="ui-cal__header">
        <button
          type="button"
          className="ui-cal__nav"
          onClick={() => setCursor(cursor.subtract(1, "month"))}
          disabled={!canPrev}
          aria-label="Previous month"
        >‹</button>
        <span className="ui-cal__month">{cursor.format("MMMM YYYY")}</span>
        <button
          type="button"
          className="ui-cal__nav"
          onClick={() => setCursor(cursor.add(1, "month"))}
          disabled={!canNext}
          aria-label="Next month"
        >›</button>
      </div>

      <div className="ui-cal__weekdays">
        {["Mo","Tu","We","Th","Fr","Sa","Su"].map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>

      <div className="ui-cal__grid">
        {cells.map((d, idx) => {
          if (!d) return <span key={idx} className="ui-cal__cell ui-cal__cell--empty" />;
          const blocked = isBlocked(d);
          const oor = isOutOfRange(d);
          const isStart = isFrom(d);
          const isEnd = isTo(d);
          const inRange = inSelected(d);
          const cls = [
            "ui-cal__cell",
            blocked || oor ? "ui-cal__cell--disabled" : "",
            isStart ? "ui-cal__cell--start" : "",
            isEnd ? "ui-cal__cell--end" : "",
            inRange ? "ui-cal__cell--in" : "",
          ].filter(Boolean).join(" ");
          return (
            <button
              key={d.format("YYYY-MM-DD")}
              type="button"
              className={cls}
              onClick={() => handlePick(d)}
              disabled={blocked || oor}
            >
              {d.date()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

Calendar.propTypes = {
  value: PropTypes.shape({ from: PropTypes.string, to: PropTypes.string }),
  onChange: PropTypes.func.isRequired,
  blockedDates: PropTypes.arrayOf(PropTypes.string),
  minDate: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
  maxDate: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
};
