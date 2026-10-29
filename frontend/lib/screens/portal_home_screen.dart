import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'portal_services.dart';

class PortalHomeScreen extends StatefulWidget {
  const PortalHomeScreen({super.key, required this.onStudent});
  final VoidCallback onStudent;
  @override
  State<PortalHomeScreen> createState() => _PortalHomeScreenState();
}

class _PortalHomeScreenState extends State<PortalHomeScreen> {
  DateTime _date = DateTime.now().toUtc().add(const Duration(hours: 8));
  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      await ApiClient.instance.loadConfig();
      final server = ApiClient.instance.config['server_time'] as String?;
      if (mounted && server != null) {
        setState(() => _date = DateTime.parse(server.substring(0, 19)));
      }
    } catch (_) {
      /* Public home content stays available while the API is offline. */
    }
  }

  @override
  Widget build(BuildContext context) {
    const weekdays = [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ];
    final shortcutHeight =
        ((MediaQuery.sizeOf(context).width - 56) / 4 / .98) * 2 + 33;
    return RefreshIndicator(
      onRefresh: _refresh,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          children: [
            SizedBox(
              height: 155 + shortcutHeight + 10,
              child: Stack(
                children: [
                  Container(
                    height: 206,
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.bottomLeft,
                        end: Alignment.topRight,
                        colors: [
                          Color(0xFF4D168D),
                          Color(0xFF210A3C),
                          Color(0xFF07040C),
                        ],
                      ),
                    ),
                  ),
                  Positioned(
                    top: 9,
                    right: 8,
                    child: IconButton(
                      onPressed: () => openAccountSettings(context),
                      tooltip: 'Account settings',
                      icon: const Icon(
                        Icons.settings,
                        color: Colors.white,
                        size: 25,
                      ),
                    ),
                  ),
                  Positioned(
                    left: 22,
                    right: 22,
                    top: 40,
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Padding(
                          padding: EdgeInsets.only(top: 7),
                          child: UniversityCrest(width: 36),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.baseline,
                                textBaseline: TextBaseline.alphabetic,
                                children: [
                                  Text(
                                    '${_date.day.toString().padLeft(2, '0')}-${_date.month.toString().padLeft(2, '0')}',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 31,
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    weekdays[_date.weekday - 1],
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 12,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 2),
                              const Text(
                                'Tunku Abdul Rahman University Of Management And Technology',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                  height: 1.1,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  Positioned(
                    top: 155,
                    left: 18,
                    right: 18,
                    child: Container(
                      padding: const EdgeInsets.fromLTRB(10, 17, 10, 10),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: GridView.count(
                        padding: EdgeInsets.zero,
                        primary: false,
                        crossAxisCount: 4,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        childAspectRatio: .98,
                        mainAxisSpacing: 6,
                        children: [
                          _shortcut(
                            'News',
                            Icons.campaign,
                            const Color(0xFF5826AA),
                            () => openUniversityLink(context, universityNews),
                          ),
                          _shortcut(
                            'Online\nApplication',
                            Icons.edit_document,
                            const Color(0xFFF04262),
                            () => openUniversityLink(
                              context,
                              'https://www.tarc.edu.my/account/login.jsp?fappcode=online-app',
                            ),
                          ),
                          _shortcut(
                            'Programme\nOffered',
                            Icons.school,
                            const Color(0xFF137FCB),
                            () => openUniversityLink(
                              context,
                              'https://www.tarc.edu.my/local-international.jsp',
                            ),
                          ),
                          _shortcut(
                            'KL Campus\nVirtual Tour',
                            Icons.language,
                            const Color(0xFF8247FF),
                            () => openUniversityLink(
                              context,
                              'https://www.tarc.edu.my/kl/',
                            ),
                          ),
                          _shortcut(
                            'Contact Us',
                            Icons.forum,
                            const Color(0xFF941C23),
                            () =>
                                openUniversityLink(context, universityContact),
                          ),
                          _shortcut(
                            'Library',
                            Icons.local_library,
                            const Color(0xFF235A8D),
                            () =>
                                openUniversityLink(context, universityLibrary),
                          ),
                          _shortcut(
                            'Events',
                            Icons.calendar_month,
                            const Color(0xFFFF8612),
                            () => openUniversityLink(
                              context,
                              'https://www.tarc.edu.my/dsa/index.jsp',
                            ),
                          ),
                          _shortcut(
                            'More',
                            Icons.more_horiz,
                            const Color(0xFF008B79),
                            widget.onStudent,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
              child: Column(
                children: [
                  _banner(context, const IntakeBanner(), universityAdmissions),
                  const SizedBox(height: 12),
                  _banner(
                    context,
                    Image.asset(
                      'assets/portal/career-interest.jpg',
                      fit: BoxFit.cover,
                    ),
                    'https://forms.gle/PYFC4WgcdYcJnaA29',
                  ),
                  const SizedBox(height: 12),
                  _banner(
                    context,
                    Image.asset(
                      'assets/portal/steam-event.jpg',
                      fit: BoxFit.cover,
                    ),
                    'https://steamtarumt.com',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _shortcut(
    String text,
    IconData icon,
    Color color,
    VoidCallback action,
  ) => InkWell(
    borderRadius: BorderRadius.circular(10),
    onTap: action,
    child: Column(
      children: [
        Container(
          width: 45,
          height: 45,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            boxShadow: const [
              BoxShadow(
                color: Color(0x22000000),
                blurRadius: 4,
                offset: Offset(0, 2),
              ),
            ],
          ),
          child: Icon(icon, color: Colors.white, size: 25),
        ),
        const SizedBox(height: 5),
        Expanded(
          child: Align(
            alignment: Alignment.topCenter,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                text,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 14, height: 1.05),
              ),
            ),
          ),
        ),
      ],
    ),
  );

  Widget _banner(BuildContext context, Widget image, String url) => Material(
    color: Colors.white,
    elevation: 2,
    shadowColor: Colors.black26,
    borderRadius: BorderRadius.circular(5),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: () => openUniversityLink(context, url),
      child: Column(
        children: [
          AspectRatio(aspectRatio: 2.48, child: image),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 18, vertical: 5),
            child: Row(
              children: [
                Text(
                  'More',
                  style: TextStyle(color: portalPurple, fontSize: 14),
                ),
                Spacer(),
                Icon(Icons.chevron_right, color: portalPurple, size: 18),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class IntakeBanner extends StatelessWidget {
  const IntakeBanner({super.key});
  @override
  Widget build(BuildContext context) => ColoredBox(
    color: const Color(0xFF2E4477),
    child: Stack(
      children: [
        const Positioned.fill(child: CustomPaint(painter: _CircuitPainter())),
        const Positioned(
          top: 10,
          left: 14,
          child: Row(
            children: [
              Icon(Icons.school, size: 17, color: Colors.white70),
              SizedBox(width: 4),
              Text(
                'TAR UMT',
                style: TextStyle(
                  fontFamily: 'Roboto',
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                  color: Colors.white,
                ),
              ),
            ],
          ),
        ),
        Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                '2026',
                style: TextStyle(
                  fontFamily: 'Roboto',
                  color: Colors.white,
                  fontSize: 38,
                  fontWeight: FontWeight.w300,
                  height: 1.05,
                ),
              ),
              const Text(
                'INTAKES',
                style: TextStyle(
                  fontFamily: 'Roboto',
                  color: Colors.white,
                  fontSize: 30,
                  fontWeight: FontWeight.w900,
                  fontStyle: FontStyle.italic,
                  height: 1,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                'I N  P R O G R E S S',
                style: TextStyle(
                  fontFamily: 'Roboto',
                  color: Colors.white.withValues(alpha: .85),
                  fontSize: 15,
                  fontWeight: FontWeight.w300,
                ),
              ),
            ],
          ),
        ),
        Positioned(
          right: 15,
          bottom: 40,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 5),
            decoration: BoxDecoration(
              border: Border.all(color: Colors.white54),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Text(
              'APPLY\nNOW',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontFamily: 'Roboto',
                fontSize: 10,
                height: 1.1,
                color: Colors.white70,
              ),
            ),
          ),
        ),
      ],
    ),
  );
}

class _CircuitPainter extends CustomPainter {
  const _CircuitPainter();
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF80D8DF).withValues(alpha: .65)
      ..strokeWidth = 1;
    for (var i = 0; i < 5; i++) {
      final y = 9.0 + i * 9;
      final x = size.width * (.18 + i * .045);
      canvas.drawLine(Offset(0, y), Offset(x, y), paint);
      canvas.drawLine(Offset(x, y), Offset(x, y + 17), paint);
      canvas.drawCircle(Offset(x, y + 17), 1.8, paint);
      canvas.drawLine(
        Offset(size.width, size.height - y),
        Offset(size.width - x, size.height - y),
        paint,
      );
      canvas.drawCircle(Offset(size.width - x, size.height - y), 2, paint);
    }
    for (var row = 0; row < 5; row++) {
      for (var col = 0; col < 8; col++) {
        canvas.drawCircle(
          Offset(10 + col * 6, size.height * .42 + row * 6),
          .7,
          paint,
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _CircuitPainter oldDelegate) => false;
}
