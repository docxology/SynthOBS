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
	float flux;
	int sunspots;
	int verdict; /* +1 constructive(AR14409), -1 destructive, 0 mixed */
	int swo_calibrated;
	int gateway_locked;
};
void fractisynth_get_state(struct fractisynth_dock_state *out);
}

/* Brand palette. */
static const QColor CHARCOAL(30, 29, 24);
static const QColor LINEN(239, 233, 220);
static const QColor ROBIN(58, 175, 169);
static const QColor MARIGOLD(232, 163, 61);
static const QColor H_ALPHA(232, 49, 58);
static const QColor BONE(150, 145, 132);

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
		setMinimumSize(232, 372);
		setCursor(Qt::PointingHandCursor);
		setToolTip(QStringLiteral("Click to cycle display: Full · Compact · Gauge"));
		startTimer(120); /* ~8 Hz; timerEvent needs no moc */
	}

protected:
	int m_mode = 0; /* 0 Full · 1 Compact · 2 Gauge-only — cycled by click (moc-free) */

	void timerEvent(QTimerEvent *) override { update(); }

	/* Click anywhere cycles the display density — the dock's in-place config. */
	void mousePressEvent(QMouseEvent *e) override
	{
		if (e->button() == Qt::LeftButton) {
			m_mode = (m_mode + 1) % 3;
			update();
		}
		QWidget::mousePressEvent(e);
	}

	/* one "label .... value" row, value right-aligned + coloured */
	void row(QPainter &p, double &y, double w, const QString &label,
		 const QString &value, const QColor &vcol)
	{
		const double h = 19.0;
		p.setPen(BONE);
		p.drawText(QRectF(12, y, w - 24, h), Qt::AlignLeft | Qt::AlignVCenter, label);
		p.setPen(vcol);
		p.drawText(QRectF(12, y, w - 24, h), Qt::AlignRight | Qt::AlignVCenter, value);
		y += h;
	}

	void paintEvent(QPaintEvent *) override
	{
		fractisynth_dock_state st;
		fractisynth_get_state(&st);

		QPainter p(this);
		p.setRenderHint(QPainter::Antialiasing, true);
		const double w = width();
		p.fillRect(rect(), CHARCOAL);

		double lock = st.lock_strength;
		if (lock < 0.0) lock = 0.0;
		if (lock > 1.0) lock = 1.0;

		/* ---- title ---- */
		QFont title = p.font();
		title.setBold(true);
		title.setPointSizeF(title.pointSizeF() + 0.5);
		p.setFont(title);
		p.setPen(LINEN);
		p.drawText(QRectF(12, 8, w - 24, 22), Qt::AlignLeft, fs("SynthOBS \xc2\xb7 EGS Gateway"));
		QFont body = p.font();
		body.setBold(false);
		body.setPointSizeF(body.pointSizeF() - 0.5);
		p.setFont(body);

		/* ---- live/validated status line ---- */
		bool live = st.swo_calibrated && st.gateway_locked;
		QColor dotc = live ? ROBIN : (st.swo_calibrated || st.gateway_locked ? MARIGOLD : H_ALPHA);
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
			H_ALPHA.redF() * (1.0 - lock) + ROBIN.redF() * lock,
			H_ALPHA.greenF() * (1.0 - lock) + ROBIN.greenF() * lock,
			H_ALPHA.blueF() * (1.0 - lock) + ROBIN.blueF() * lock);
		QRectF ring(cx - R, cy - R, 2 * R, 2 * R);
		QPen base(QColor(0, 0, 0, 120));
		base.setWidthF(8);
		p.setPen(base);
		p.setBrush(Qt::NoBrush);
		p.drawEllipse(ring);
		QPen arc(st.gateway_locked ? lk : QColor(120, 40, 44));
		arc.setWidthF(8);
		arc.setCapStyle(Qt::RoundCap);
		p.setPen(arc);
		p.drawArc(ring, 90 * 16, -static_cast<int>(lock * 360.0 * 16.0));
		if (st.gateway_locked) {
			QPen sp(MARIGOLD);
			sp.setWidthF(1.3);
			p.setPen(sp);
			QPointF prev;
			bool have = false;
			for (int i = 0; i < 70; ++i) {
				double t = i / 69.0;
				double a = t * TAU * 1.5 + st.wind_phase;
				double rr = R * 0.78 * std::pow(1.0 / 1.61803398875, t * 4.0);
				QPointF cur(cx + rr * std::cos(a), cy + rr * std::sin(a));
				if (have)
					p.drawLine(prev, cur);
				prev = cur;
				have = true;
			}
		}
		p.setPen(LINEN);
		p.drawText(QRectF(0, cy + R + 2, w, 16), Qt::AlignHCenter,
			   st.gateway_locked ? fs("lock %.0f%%", lock * 100.0) : fs("\xe2\x80\x94 acquiring"));

		/* ---- numeric readout (density set by the click-cycled mode) ---- */
		const char *vt = st.verdict > 0 ? "CONSTRUCTIVE" : st.verdict < 0 ? "DESTRUCTIVE" : "MIXED";
		QColor vc = st.verdict > 0 ? ROBIN : st.verdict < 0 ? H_ALPHA : BONE;
		double y = cy + R + 24;
		if (m_mode == 0) { /* Full */
			row(p, y, w, fs("SWO phase vector"),
			    st.swo_calibrated ? fs("%.4f", st.phase_vector) : fs("\xe2\x80\x94 hold"),
			    st.swo_calibrated ? MARIGOLD : H_ALPHA);
			row(p, y, w, fs("F10.7 flux (sfu)"),
			    st.swo_calibrated ? fs("%.1f", st.flux) : fs("\xe2\x80\x94"), LINEN);
			row(p, y, w, fs("active sunspots"),
			    st.swo_calibrated ? fs("%d", st.sunspots) : fs("\xe2\x80\x94"), LINEN);
			row(p, y, w, fs("solar wind (km/s)"),
			    st.gateway_locked ? fs("%.1f", st.solar_wind_kms) : fs("\xe2\x80\x94 hold"), LINEN);
			row(p, y, w, fs("lock strength"), fs("%.3f", lock),
			    st.gateway_locked ? lk : H_ALPHA);
			row(p, y, w, fs("phase bias \xce\xb8"), fs("%.3f rad", st.wind_phase), LINEN);
			row(p, y, w, fs("holographic gate"), fs("%s", vt), st.gateway_locked ? vc : BONE);
			row(p, y, w, fs("K_EGS  \xcf\x86\xc2\xb7\xce\xbbr/\xce\xbbH\xce\xb1"), fs("%.4f", (double)K_EGS), ROBIN);
		} else if (m_mode == 1) { /* Compact — the essentials */
			row(p, y, w, fs("flux / spots"),
			    st.swo_calibrated ? fs("%.0f / %d", st.flux, st.sunspots) : fs("\xe2\x80\x94"), LINEN);
			row(p, y, w, fs("solar wind"),
			    st.gateway_locked ? fs("%.0f km/s", st.solar_wind_kms) : fs("\xe2\x80\x94"), LINEN);
			row(p, y, w, fs("lock strength"), fs("%.3f", lock), st.gateway_locked ? lk : H_ALPHA);
			row(p, y, w, fs("holographic gate"), fs("%s", vt), st.gateway_locked ? vc : BONE);
		}
		/* m_mode == 2 (Gauge-only): no rows — just the gauge + lock%. */

		/* mode hint */
		const char *mn = m_mode == 0 ? "full" : m_mode == 1 ? "compact" : "gauge";
		p.setPen(BONE);
		p.drawText(QRectF(12, height() - 18, w - 24, 14),
			   Qt::AlignRight | Qt::AlignVCenter, fs("\xe2\x97\x89 %s \xc2\xb7 click to cycle", mn));

		p.setPen(QColor(58, 175, 169, 110));
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
