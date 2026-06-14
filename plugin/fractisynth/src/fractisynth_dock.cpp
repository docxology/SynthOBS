/*
 * FractiSynth frontend dock — a live "El Gran Sol Gateway" telemetry panel in the
 * OBS window chrome (Docks → SynthOBS Gateway).
 *
 * A moc-free QWidget (overrides only paintEvent + timerEvent — no signals/slots, so
 * no moc step) that paints the live transducer state read from the mutex-guarded C
 * accessor fractisynth_get_state(): a gateway lock-ring gauge plus a numeric readout
 * of the SWO phase vector, F10.7 flux, active sunspots, solar wind, lock strength,
 * phase bias, the holographic interference verdict, and the gateway key K_EGS.
 *
 * The dock is compiled ONLY against a Qt whose major.minor matches OBS's bundled
 * runtime (build.sh gate; obs-deps Qt 6.8 is auto-used from .obs-sdk/qt-6.8). With a
 * matching Qt the full QString/text API is safe; a mismatched Qt is skipped at build
 * time so the core plugin always loads. Registered via obs_module_post_load().
 */

#include <QWidget>
#include <QDockWidget>
#include <QMainWindow>
#include <QPainter>
#include <QPaintEvent>
#include <QTimerEvent>
#include <QMouseEvent>
#include <QColor>
#include <QFont>
#include <QString>
#include <QRectF>
#include <QPointF>

#include <cmath>
#include <cstdarg>
#include <cstdio>

extern "C" {
#include <obs-module.h>
#include "obs-frontend-api.h"

/* Mirror of struct fractisynth_dock_state in fractisynth.c (identical layout). */
struct fractisynth_dock_state {
	float phase_vector;
	float lock_strength;
	float wind_phase;
	float solar_wind_kms;
	float audio_rms;
	float audio_peak;
	float audio_reactivity;
	float flux;
	int sunspots;
	int verdict; /* +1 constructive(AR14409), -1 destructive, 0 mixed */
	int swo_calibrated;
	int gateway_locked;
	int audio_active;
};
void fractisynth_get_state(struct fractisynth_dock_state *out);
int fractisynth_get_console_theme(void);
int fractisynth_get_series(int metric, float *out, int max); /* 0 wind,1 dens,2 temp,3 X-ray,4 Kp */
}

struct DockPalette {
	QColor charcoal;
	QColor linen;
	QColor robin;
	QColor marigold;
	QColor h_alpha;
	QColor bone;
};

static DockPalette palette_for_theme(int theme)
{
	switch (theme) {
	case 1: /* Laboratory */
		return {QColor(18, 24, 31), QColor(226, 236, 242), QColor(86, 166, 214),
			QColor(172, 190, 206), QColor(235, 90, 88), QColor(136, 154, 166)};
	case 2: /* Expedition */
		return {QColor(34, 23, 18), QColor(246, 232, 209), QColor(235, 124, 68),
			QColor(244, 183, 74), QColor(215, 58, 48), QColor(166, 132, 104)};
	default: /* Observatory */
		return {QColor(30, 29, 24), QColor(239, 233, 220), QColor(58, 175, 169),
			QColor(232, 163, 61), QColor(232, 49, 58), QColor(150, 145, 132)};
	}
}

static const double TAU = 6.28318530717958647692;
#define K_EGS 2.539427

/* printf into a QString (avoids the QString::arg/number template machinery). */
static QString fs(const char *fmt, ...)
{
	char buf[160];
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	return QString::fromUtf8(buf);
}

class FractiSynthDock : public QWidget {
public:
	explicit FractiSynthDock(QWidget *parent = nullptr) : QWidget(parent)
	{
		setObjectName(QStringLiteral("FractiSynthDock"));
		setMinimumSize(232, 392);
		setMouseTracking(true);
		startTimer(120); /* ~8 Hz; timerEvent needs no moc */
	}

protected:
	int m_mode = 0;        /* 0 Full · 1 Compact · 2 Gauge-only */
	int m_gauge_style = 0; /* 0 Ring · 1 Bar · 2 Needle */
	int m_precision = 1;   /* 0, 1, or 2 decimal places */
	bool m_freeze = false; /* hold the last snapshot */
	int m_hover = -1;      /* hovered button index */
	QRectF m_btn[6];       /* button hit-rects, laid out in paintEvent */
	fractisynth_dock_state m_cached{};
	bool m_have_cached = false;

	void timerEvent(QTimerEvent *) override { update(); }

	int hit(const QPointF &pt) const
	{
		for (int i = 0; i < 6; ++i)
			if (m_btn[i].contains(pt))
				return i;
		return -1;
	}

	QString num(double value) const
	{
		return fs("%.*f", m_precision, value);
	}

	QString num_unit(double value, const char *unit) const
	{
		return fs("%.*f %s", m_precision, value, unit);
	}

	/* Real buttons: display mode, Freeze, gauge style, and decimal precision —
	 * the dock as an interactive config pane (moc-free; paintEvent lays out the
	 * hit-rects). */
	void mousePressEvent(QMouseEvent *e) override
	{
		if (e->button() == Qt::LeftButton) {
			int b = hit(e->position());
			if (b >= 0 && b <= 2)
				m_mode = b;
			else if (b == 3)
				m_freeze = !m_freeze;
			else if (b == 4)
				m_gauge_style = (m_gauge_style + 1) % 3;
			else if (b == 5)
				m_precision = (m_precision + 1) % 3;
			update();
		}
		QWidget::mousePressEvent(e);
	}

	void mouseMoveEvent(QMouseEvent *e) override
	{
		int h = hit(e->position());
		if (h != m_hover) {
			m_hover = h;
			setCursor(h >= 0 ? Qt::PointingHandCursor : Qt::ArrowCursor);
			update();
		}
		QWidget::mouseMoveEvent(e);
	}

	/* draw one button; returns nothing — rect already stored in m_btn[idx] */
	void button(QPainter &p, int idx, const QString &label, bool on, const DockPalette &pal)
	{
		QRectF r = m_btn[idx];
		QColor fill = on ? pal.robin : QColor(48, 47, 40);
		if (m_hover == idx)
			fill = fill.lighter(125);
		p.setPen(Qt::NoPen);
		p.setBrush(fill);
		p.drawRoundedRect(r, 4, 4);
		p.setPen(on ? pal.charcoal : pal.linen);
		p.drawText(r, Qt::AlignCenter, label);
	}

	/* one "label .... value" row, value right-aligned + coloured */
	void row(QPainter &p, double &y, double w, const QString &label,
		 const QString &value, const QColor &vcol, const DockPalette &pal)
	{
		const double h = 19.0;
		p.setPen(pal.bone);
		p.drawText(QRectF(12, y, w - 24, h), Qt::AlignLeft | Qt::AlignVCenter, label);
		p.setPen(vcol);
		p.drawText(QRectF(12, y, w - 24, h), Qt::AlignRight | Qt::AlignVCenter, value);
		y += h;
	}

	void drawGauge(QPainter &p, const DockPalette &pal, double cx, double cy,
		       double R, double lock, const QColor &lk, bool gateway_locked,
		       float wind_phase)
	{
		if (m_gauge_style == 1) {
			QRectF track(cx - R, cy - 10, 2 * R, 20);
			p.setPen(Qt::NoPen);
			p.setBrush(QColor(0, 0, 0, 130));
			p.drawRoundedRect(track, 7, 7);
			QRectF fill(track.left(), track.top(), track.width() * lock, track.height());
			p.setBrush(gateway_locked ? lk : pal.h_alpha.darker(140));
			p.drawRoundedRect(fill, 7, 7);
			p.setPen(pal.bone);
			for (int i = 0; i <= 4; ++i) {
				double x = track.left() + track.width() * i / 4.0;
				p.drawLine(QPointF(x, track.bottom() + 3), QPointF(x, track.bottom() + 9));
			}
			return;
		}
		if (m_gauge_style == 2) {
			QRectF arcbox(cx - R, cy - R * 0.55, 2 * R, 2 * R);
			QPen base(QColor(0, 0, 0, 120));
			base.setWidthF(7);
			p.setPen(base);
			p.setBrush(Qt::NoBrush);
			p.drawArc(arcbox, 210 * 16, -240 * 16);
			QPen arc(gateway_locked ? lk : pal.h_alpha.darker(140));
			arc.setWidthF(7);
			arc.setCapStyle(Qt::RoundCap);
			p.setPen(arc);
			p.drawArc(arcbox, 210 * 16, -static_cast<int>(lock * 240.0 * 16.0));
			double a = (210.0 - 240.0 * lock) * TAU / 360.0;
			QPen needle(pal.marigold);
			needle.setWidthF(2.0);
			p.setPen(needle);
			p.drawLine(QPointF(cx, cy),
				   QPointF(cx + R * 0.72 * std::cos(a),
					   cy - R * 0.72 * std::sin(a)));
			p.setBrush(pal.linen);
			p.setPen(Qt::NoPen);
			p.drawEllipse(QPointF(cx, cy), 3.5, 3.5);
			return;
		}

		QRectF ring(cx - R, cy - R, 2 * R, 2 * R);
		QPen base(QColor(0, 0, 0, 120));
		base.setWidthF(8);
		p.setPen(base);
		p.setBrush(Qt::NoBrush);
		p.drawEllipse(ring);
		QPen arc(gateway_locked ? lk : pal.h_alpha.darker(140));
		arc.setWidthF(8);
		arc.setCapStyle(Qt::RoundCap);
		p.setPen(arc);
		p.drawArc(ring, 90 * 16, -static_cast<int>(lock * 360.0 * 16.0));
		if (gateway_locked) {
			QPen sp(pal.marigold);
			sp.setWidthF(1.3);
			p.setPen(sp);
			QPointF prev;
			bool have = false;
			for (int i = 0; i < 70; ++i) {
				double t = i / 69.0;
				double a = t * TAU * 1.5 + wind_phase;
				double rr = R * 0.78 * std::pow(1.0 / 1.61803398875, t * 4.0);
				QPointF cur(cx + rr * std::cos(a), cy + rr * std::sin(a));
				if (have)
					p.drawLine(prev, cur);
				prev = cur;
				have = true;
			}
		}
	}

	void paintEvent(QPaintEvent *) override
	{
		fractisynth_dock_state st;
		if (m_freeze && m_have_cached) {
			st = m_cached; /* hold the snapshot */
		} else {
			fractisynth_get_state(&st);
			m_cached = st;
			m_have_cached = true;
		}

		QPainter p(this);
		p.setRenderHint(QPainter::Antialiasing, true);
		const double w = width();
		DockPalette pal = palette_for_theme(fractisynth_get_console_theme());
		p.fillRect(rect(), pal.charcoal);

		double lock = st.lock_strength;
		if (lock < 0.0) lock = 0.0;
		if (lock > 1.0) lock = 1.0;
		double audio = st.audio_reactivity;
		if (audio < 0.0) audio = 0.0;
		if (audio > 1.0) audio = 1.0;

		/* ---- title ---- */
		QFont title = p.font();
		title.setBold(true);
		title.setPointSizeF(title.pointSizeF() + 0.5);
		p.setFont(title);
		p.setPen(pal.linen);
		p.drawText(QRectF(12, 8, w - 24, 22), Qt::AlignLeft, fs("SynthOBS \xc2\xb7 EGS Gateway"));
		QFont body = p.font();
		body.setBold(false);
		body.setPointSizeF(body.pointSizeF() - 0.5);
		p.setFont(body);

		/* ---- live/validated status line ---- */
		bool live = st.swo_calibrated && st.gateway_locked;
		QColor dotc = live ? pal.robin : (st.swo_calibrated || st.gateway_locked ? pal.marigold : pal.h_alpha);
		p.setPen(Qt::NoPen);
		p.setBrush(dotc);
		p.drawEllipse(QPointF(16, 36), 4, 4);
		p.setPen(dotc);
		p.drawText(QRectF(26, 28, w - 38, 16), Qt::AlignLeft | Qt::AlignVCenter,
			   live ? fs("LIVE \xc2\xb7 NOAA SWPC verified")
				: st.swo_calibrated || st.gateway_locked
					  ? fs("partial \xc2\xb7 acquiring")
					  : fs("acquiring telemetry\xe2\x80\xa6"));

		/* ---- lock-ring gauge ---- */
		const double cx = w * 0.5, cy = 108.0, R = 46.0;
		QColor lk = QColor::fromRgbF(
			pal.h_alpha.redF() * (1.0 - lock) + pal.robin.redF() * lock,
			pal.h_alpha.greenF() * (1.0 - lock) + pal.robin.greenF() * lock,
			pal.h_alpha.blueF() * (1.0 - lock) + pal.robin.blueF() * lock);
		drawGauge(p, pal, cx, cy, R, lock, lk, st.gateway_locked, st.wind_phase);
		p.setPen(pal.linen);
		p.drawText(QRectF(0, cy + R + 2, w, 16), Qt::AlignHCenter,
			   st.gateway_locked ? fs("lock %.0f%%", lock * 100.0) : fs("\xe2\x80\x94 acquiring"));
		QRectF atrack(24, cy + R + 20, w - 48, 5);
		p.setPen(Qt::NoPen);
		p.setBrush(QColor(0, 0, 0, 120));
		p.drawRoundedRect(atrack, 2, 2);
		p.setBrush(st.audio_active ? pal.marigold : pal.h_alpha.darker(140));
		p.drawRoundedRect(QRectF(atrack.left(), atrack.top(), atrack.width() * audio,
					 atrack.height()), 2, 2);

		/* ---- numeric readout (density set by the click-cycled mode) ---- */
		const char *vt = st.verdict > 0 ? "CONSTRUCTIVE" : st.verdict < 0 ? "DESTRUCTIVE" : "MIXED";
		QColor vc = st.verdict > 0 ? pal.robin : st.verdict < 0 ? pal.h_alpha : pal.bone;
		double y = cy + R + 24;
		if (m_mode == 0) { /* Full */
			row(p, y, w, fs("SWO phase vector"),
			    st.swo_calibrated ? num(st.phase_vector) : fs("\xe2\x80\x94 hold"),
			    st.swo_calibrated ? pal.marigold : pal.h_alpha, pal);
			row(p, y, w, fs("F10.7 flux (sfu)"),
			    st.swo_calibrated ? num(st.flux) : fs("\xe2\x80\x94"), pal.linen, pal);
			row(p, y, w, fs("active sunspots"),
			    st.swo_calibrated ? fs("%d", st.sunspots) : fs("\xe2\x80\x94"), pal.linen, pal);
			row(p, y, w, fs("solar wind (km/s)"),
			    st.gateway_locked ? num(st.solar_wind_kms) : fs("\xe2\x80\x94 hold"), pal.linen, pal);
			row(p, y, w, fs("lock strength"), num(lock),
			    st.gateway_locked ? lk : pal.h_alpha, pal);
			row(p, y, w, fs("phase bias \xce\xb8"), num_unit(st.wind_phase, "rad"), pal.linen, pal);
			row(p, y, w, fs("holographic gate"), fs("%s", vt), st.gateway_locked ? vc : pal.bone, pal);
			row(p, y, w, fs("K_EGS  \xcf\x86\xc2\xb7\xce\xbbr/\xce\xbbH\xce\xb1"), num((double)K_EGS), pal.robin, pal);
			QString audio_pair = fs("%.3f / %.3f", (double)st.audio_rms, (double)st.audio_peak);
			row(p, y, w, fs("audio rms / peak"),
			    st.audio_active ? audio_pair : fs("\xe2\x80\x94"), st.audio_active ? pal.marigold : pal.bone, pal);
			row(p, y, w, fs("audio reactivity"),
			    st.audio_active ? num(audio) : fs("\xe2\x80\x94"), st.audio_active ? pal.marigold : pal.bone, pal);
			/* live realtime solar-wind graph (real NOAA 2 h series) */
			y += 8;
			double gx = 12, gw = w - 24;
			double gyt = y, ght = height() - 38 - gyt - 6;
			if (ght > 28) {
				p.setPen(pal.bone);
				p.drawText(QRectF(gx, gyt, gw, 12), Qt::AlignLeft,
					   fs("solar wind \xc2\xb7 NOAA 2h"));
				double gby = gyt + 14, gbh = ght - 14;
				p.fillRect(QRectF(gx, gby, gw, gbh), QColor(14, 14, 11));
				float s[256];
				int n = fractisynth_get_series(0, s, 256);
				if (n >= 2) {
					float mn = s[0], mx = s[0];
					for (int i = 1; i < n; ++i) {
						if (s[i] < mn) mn = s[i];
						if (s[i] > mx) mx = s[i];
					}
					double rng = mx - mn;
					QPen gp(pal.robin); gp.setWidthF(1.4); p.setPen(gp);
					QPointF prev; bool have = false;
					for (int i = 0; i < n; ++i) {
						double nrm = rng > 1e-6 ? (s[i] - mn) / rng : 0.5;
						double px = gx + gw * i / (n - 1);
						double py = gby + gbh - 1 - nrm * (gbh - 1);
						QPointF cur(px, py);
						if (have) p.drawLine(prev, cur);
						prev = cur; have = true;
					}
					p.setPen(pal.robin);
					p.drawText(QRectF(gx + 4, gby + 2, gw - 8, 12), Qt::AlignRight,
						   num_unit((double)s[n - 1], "km/s"));
				} else {
					p.setPen(pal.marigold);
					p.drawText(QRectF(gx, gby, gw, gbh), Qt::AlignCenter, fs("acquiring series\xe2\x80\xa6"));
				}
			}
		} else if (m_mode == 1) { /* Compact — the essentials */
			QString flux_value = st.swo_calibrated ? num(st.flux) : fs("");
			row(p, y, w, fs("flux / spots"),
			    st.swo_calibrated ? fs("%s / %d", flux_value.toUtf8().constData(), st.sunspots) : fs("\xe2\x80\x94"),
			    pal.linen, pal);
			row(p, y, w, fs("solar wind"),
			    st.gateway_locked ? num_unit(st.solar_wind_kms, "km/s") : fs("\xe2\x80\x94"),
			    pal.linen, pal);
			row(p, y, w, fs("lock strength"), num(lock), st.gateway_locked ? lk : pal.h_alpha, pal);
			row(p, y, w, fs("audio react"), st.audio_active ? num(audio) : fs("\xe2\x80\x94"),
			    st.audio_active ? pal.marigold : pal.bone, pal);
			row(p, y, w, fs("holographic gate"), fs("%s", vt), st.gateway_locked ? vc : pal.bone, pal);
		}
		/* m_mode == 2 (Gauge-only): no rows — just the gauge + lock%. */

		/* ---- interactive button row (the dock's config pane) ---- */
		const double bh = 22, by2 = height() - bh - 8, by1 = by2 - bh - 5, gap = 5;
		const double bw = (w - 24 - 3 * gap) / 4.0;
		for (int i = 0; i < 4; ++i)
			m_btn[i] = QRectF(12 + i * (bw + gap), by1, bw, bh);
		const double bw2 = (w - 24 - gap) / 2.0;
		m_btn[4] = QRectF(12, by2, bw2, bh);
		m_btn[5] = QRectF(12 + bw2 + gap, by2, bw2, bh);
		QFont bf = p.font();
		bf.setPointSizeF(bf.pointSizeF() - 1.0);
		p.setFont(bf);
		button(p, 0, fs("Full"), m_mode == 0, pal);
		button(p, 1, fs("Compact"), m_mode == 1, pal);
		button(p, 2, fs("Gauge"), m_mode == 2, pal);
		button(p, 3, m_freeze ? fs("\xe2\x96\xb6 Live") : fs("\xe2\x9d\x9a Hold"), m_freeze, pal);
		const char *style = m_gauge_style == 1 ? "Bar" : m_gauge_style == 2 ? "Needle" : "Ring";
		button(p, 4, fs("Style %s", style), true, pal);
		button(p, 5, fs("%d dp", m_precision), true, pal);
		p.setFont(body);

		p.setPen(QColor(pal.robin.red(), pal.robin.green(), pal.robin.blue(), 110));
		double gx = 12 + (w - 24) * 0.618;
		p.drawLine(QPointF(gx, y + 4), QPointF(gx, y + 14));
	}
};

extern "C" {

/* OBS calls obs_module_post_load() once the Qt frontend is ready; we define it
 * here in the C++ TU (fractisynth.c does not).
 *
 * We MUST use obs_frontend_add_dock_by_id (NOT add_custom_qdock): only the former
 * calls OBSBasic::AddDockWidget, which registers the dock's toggle in the **Docks
 * menu** (menuDocks->addAction(toggleViewAction())). add_custom_qdock just adds the
 * widget to the window and an internal list — it never appears in the menu, so the
 * user can't find it. add_dock_by_id creates the OBSDock hidden+floating; we then
 * look it up by objectName and dock it on the right + SHOW it so it's visible
 * immediately (and toggleable from the Docks menu thereafter). A fresh, unique id
 * avoids any stale persisted-id collision from earlier builds. */
__attribute__((visibility("default"))) void obs_module_post_load(void)
{
	QMainWindow *main = static_cast<QMainWindow *>(obs_frontend_get_main_window());
	if (!main) {
		blog(LOG_WARNING, "[fractisynth] no main window — dock not added");
		return;
	}

	const char *id = "synthobs_gateway_dock";
	FractiSynthDock *widget = new FractiSynthDock();
	if (!obs_frontend_add_dock_by_id(id, "SynthOBS Gateway", widget)) {
		blog(LOG_WARNING, "[fractisynth] add_dock_by_id failed (id already in use?)");
		delete widget;
		return;
	}

	/* Make it visible by default: find the OBSDock OBS created and show it. */
	QDockWidget *dock = main->findChild<QDockWidget *>(QString::fromUtf8(id));
	if (dock) {
		main->addDockWidget(Qt::RightDockWidgetArea, dock);
		dock->setFloating(false);
		dock->setVisible(true);
		dock->raise();
		blog(LOG_INFO, "[fractisynth] dock registered in Docks menu + shown (right)");
	} else {
		blog(LOG_INFO, "[fractisynth] dock registered (enable via Docks menu)");
	}
}
}
