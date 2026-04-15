import './RatingTag.css';

const RATING_COLORS = {
  '买入': { bg: '#f6ffed', color: '#52c41a', border: '#b7eb8f' },
  '增持': { bg: '#f6ffed', color: '#95de64', border: '#d9f7be' },
  '中性': { bg: '#fafafa', color: '#999', border: '#d9d9d9' },
  '减持': { bg: '#fff7e6', color: '#fa8c16', border: '#ffd591' },
  '卖出': { bg: '#fff1f0', color: '#ff4d4f', border: '#ffa39e' },
};

export default function RatingTag({ rating }) {
  if (!rating) return <span className="rating-tag rating-unknown">未知</span>;
  const style = RATING_COLORS[rating] || RATING_COLORS['中性'];
  return (
    <span
      className="rating-tag"
      style={{ background: style.bg, color: style.color, borderColor: style.border }}
    >
      {rating}
    </span>
  );
}
