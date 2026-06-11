/*
 * FractiSynth frontend dock — an optional Qt6 pane in the OBS window chrome.
 *
 * A moc-free, TEXT-FREE QWidget (overrides paintEvent + timerEvent only) that
 * paints the live El Gran Sol Gateway state as a graphical gauge: a gateway lock
 * ring whose arc sweep and colour track lock_strength, a rotating φ-spiral driven
 * by the SWO phase vector, a solar-wind bar, and the golden 61.8 % split tick.
 *
 * Why text-free: OBS bundles Qt 6.8, but only Qt 6.11 dev headers are available
 * here. Every QString-touching call (drawText, setObjectName, arg, fromUtf8…)
 * inlines to QAnyStringView/QByteArrayView overloads ADDED after 6.8, which are
 * absent from OBS's runtime Qt and make the whole module fail to dlopen. Pure
 * QPainter geometry (fillRect, drawArc, drawEllipse, drawLine) uses only symbols
 * stable since Qt 4, so it loads cleanly against the 6.8 runtime. Build against a
 * matching Qt 6.8 (set QT_PREFIX) to re-enable a richer text dock.
 *
 * Registered via obs_frontend_add_dock_by_id() in obs_module_post_load(), which
 * OBS calls once the Qt frontend is ready. Compiled only when Qt6 is available;
 * if it is absent the core C plugin (filters + console source) builds and loads
 * exactly as before — the dock is purely additive.
 */

#include <QWidget>
#include <QPainter>
#include <QPaintEvent>
#include <QTimerEvent>
#include <QColor>
#include <QRectF>
#include <QPointF>

#include <cmath>

extern "C" {
#include <obs-module.h>
#include "obs-frontend-api.h"

/* Mirror of struct fractisynth_dock_state in fractisynth.c (identical layout). */
struct fractisynth_dock_state {
	float phase_vector;
	float lock_strength;
	float wind_phase;
	float solar_wind_kms;
	int swo_calibrated;
	int gateway_locked;
};
void fractisynth_get_state(struct fractisynth_dock_state *out);
}

/* Brand palette (matches the shaders / figures). */
static const QColor CHARCOAL(30, 29, 24);
static const QColor LINEN(239, 233, 220);
static const QColor ROBIN(58, 175, 169);
static const QColor MARIGOLD(232, 163, 61);
static const QColor H_ALPHA(232, 49, 58);
static const QColor BONE(150, 145, 132);

static const double TAU = 6.28318530717958647692;

class FractiSynthDock : public QWidget {
public:
	explicit FractiSynthDock(QWidget *parent = nullptr) : QWidget(parent)
	{
		setMinimumSize(180, 200);
		startTimer(150); /* repaint ~6.6 Hz; timerEvent needs no moc */
	}

protected:
	void timerEvent(QTimerEvent *) override { update(); }

	void paintEvent(QPaintEvent *) override
	{
		fractisynth_dock_state st;
		fractisynth_get_state(&st);

		QPainter p(this);
		p.setRenderHint(QPainter::Antialiasing, true);
		const double w = width();
		const double h = height();
		p.fillRect(rect(), CHARCOAL);

		double lock = st.lock_strength;
		if (lock < 0.0) lock = 0.0;
		if (lock > 1.0) lock = 1.0;
		double phaseNorm = st.swo_calibrated ? std::fmin(st.phase_vector / 1.0, 1.0) : 0.0;
		if (phaseNorm < 0.0) phaseNorm = 0.0;

		const double cx = w * 0.5;
		const double cy = h * 0.42;
		const double R = std::fmin(w, h) * 0.34;

		/* red → teal as the gateway phase-locks */
		QColor lk = QColor::fromRgbF(
			H_ALPHA.redF() * (1.0 - lock) + ROBIN.redF() * lock,
			H_ALPHA.greenF() * (1.0 - lock) + ROBIN.greenF() * lock,
			H_ALPHA.blueF() * (1.0 - lock) + ROBIN.blueF() * lock);

		/* ---- gateway lock RING: dim full circle + bright arc = lock ---- */
		QRectF ring(cx - R, cy - R, 2 * R, 2 * R);
		QPen base(QColor(0, 0, 0, 110));
		base.setWidthF(R * 0.16);
		p.setPen(base);
		p.setBrush(Qt::NoBrush);
		p.drawEllipse(ring);

		QPen arcPen(st.gateway_locked ? lk : QColor(120, 40, 44));
		arcPen.setWidthF(R * 0.16);
		arcPen.setCapStyle(Qt::RoundCap);
		p.setPen(arcPen);
		/* Qt angles are in 1/16°, CCW from 3 o'clock. Start at top (90°). */
		int startA = 90 * 16;
		int spanA = -static_cast<int>(lock * 360.0 * 16.0);
		p.drawArc(ring, startA, spanA);

		/* ---- φ-spiral inside the ring, rotated by the wind phase -------- */
		if (st.gateway_locked || st.swo_calibrated) {
			QPen sp(MARIGOLD);
			sp.setWidthF(1.6);
			p.setPen(sp);
			const double PHI = 1.61803398875;
			QPointF prev;
			bool have = false;
			const int N = 90;
			for (int i = 0; i < N; ++i) {
				double t = (double)i / (double)(N - 1);
				double ang = t * TAU * 1.5 + st.wind_phase;
				double rr = R * 0.82 * std::pow(1.0 / PHI, t * 4.0);
				QPointF cur(cx + rr * std::cos(ang), cy + rr * std::sin(ang));
				if (have)
					p.drawLine(prev, cur);
				prev = cur;
				have = true;
			}
		}

		/* ---- centre dot: phase-vector amplitude ------------------------ */
		double dotR = R * (0.10 + 0.22 * phaseNorm);
		p.setPen(Qt::NoPen);
		p.setBrush(st.swo_calibrated ? LINEN : QColor(90, 86, 78));
		p.drawEllipse(QPointF(cx, cy), dotR, dotR);

		/* ---- bottom: solar-wind bar + 61.8% golden split tick ---------- */
		double by = h - 26;
		QRectF barBg(14, by, w - 28, 9);
		p.setPen(Qt::NoPen);
		p.setBrush(QColor(0, 0, 0, 110));
		p.drawRect(barBg);
		/* map wind 250..750 km/s → 0..1 for a visible fill */
		double wf = st.gateway_locked ? (st.solar_wind_kms - 250.0) / 500.0 : 0.0;
		if (wf < 0.0) wf = 0.0;
		if (wf > 1.0) wf = 1.0;
		p.setBrush(ROBIN);
		p.drawRect(QRectF(14, by, (w - 28) * wf, 9));

		/* golden 61.8% split tick across the whole pane */
		QPen gp(QColor(58, 175, 169, 120));
		gp.setWidthF(1.0);
		p.setPen(gp);
		double gx = 14 + (w - 28) * 0.618;
		p.drawLine(QPointF(gx, by - 6), QPointF(gx, by + 15));

		/* calibration heartbeat tick (marigold when amplitude-locked) */
		p.setPen(Qt::NoPen);
		p.setBrush(st.swo_calibrated ? MARIGOLD : QColor(90, 40, 44));
		p.drawEllipse(QPointF(18.0, 16.0), 4.0, 4.0);
	}
};

extern "C" {

/* OBS calls obs_module_post_load() once the Qt frontend is ready; we define it
 * here in the C++ TU (fractisynth.c does not). */
__attribute__((visibility("default"))) void obs_module_post_load(void)
{
	FractiSynthDock *dock = new FractiSynthDock();
	/* The id/title are plain C strings handed to the C frontend API — no QString. */
	if (!obs_frontend_add_dock_by_id("fractisynth_dock",
					 "SynthOBS Gateway", dock)) {
		blog(LOG_WARNING, "[fractisynth] could not add frontend dock");
		delete dock;
	} else {
		blog(LOG_INFO, "[fractisynth] frontend dock registered");
	}
}
}
