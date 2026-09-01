"""
Email templates for GradeForAI.
Used by the dashboard API to send scorecard and report emails via Resend.
"""


def _band_color(score):
    """Return color for a score based on capability band (design token system)."""
    if score >= 90: return "#4353FE"   # brand blue - Agent Preferred
    if score >= 70: return "#6B78FE"   # blue tint - Agent Optimized
    if score >= 50: return "#E59F26"   # amber - Agent Ready
    if score >= 30: return "#D17A2E"   # orange - Agent Functional
    if score >= 10: return "#DB4850"   # red - Agent Detected
    return "#A8323A"                   # dark red - Agent Incompatible


def scorecard_email_html(domain, score, grade, dimensions):
    """Free scorecard email sent after email capture on results page."""
    color = _band_color(score)

    dim_rows = ""
    for dim in dimensions:
        name = dim.get("name", "")
        dim_score = dim.get("score")
        if dim_score is None:
            dim_rows += f"""
                                <tr>
                                    <td style="padding:8px 0;font-size:14px;color:#4a5568;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">{name}</td>
                                    <td colspan="2" style="padding:8px 0;text-align:right;font-size:13px;color:#a0aec0;font-style:italic;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Insufficient data</td>
                                </tr>"""
            continue
        bar_pct = max(2, dim_score)
        dim_color = _band_color(dim_score)
        dim_rows += f"""
                                <tr>
                                    <td style="padding:8px 0;font-size:14px;color:#4a5568;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">{name}</td>
                                    <td style="padding:8px 0;width:50%;">
                                        <table cellpadding="0" cellspacing="0" border="0" style="width:100%;">
                                            <tr>
                                                <td style="background:#e2e8f0;border-radius:4px;height:8px;width:100%;padding:0;">
                                                    <table cellpadding="0" cellspacing="0" border="0" style="width:{bar_pct}%;">
                                                        <tr><td style="background:{dim_color};border-radius:4px;height:8px;font-size:1px;line-height:1px;">&nbsp;</td></tr>
                                                    </table>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                    <td style="padding:8px 0;text-align:right;font-weight:700;font-size:14px;color:{dim_color};padding-left:12px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">{dim_score}</td>
                                </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#ffffff;">
    <tr>
        <td align="center" style="padding:32px 16px;">
            <table cellpadding="0" cellspacing="0" border="0" width="560" style="max-width:560px;width:100%;">

                <!-- Logo -->
                <tr>
                    <td align="center" style="padding-bottom:32px;">
                        <a href="https://gradeforai.com" style="text-decoration:none;"><img src="https://gradeforai.com/assets/gradeforai-logo-email.png" alt="GradeForAI" width="180" style="display:block;margin:0 auto;border:0;" /></a>
                    </td>
                </tr>

                <!-- Score Card -->
                <tr>
                    <td style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:32px;text-align:center;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr><td align="center" style="font-size:13px;color:#a0aec0;padding-bottom:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">{domain}</td></tr>
                            <tr>
                                <td align="center" style="padding-bottom:8px;">
                                    <table cellpadding="0" cellspacing="0" border="0">
                                        <tr>
                                            <td align="center" style="width:140px;height:140px;border-radius:70px;border:8px solid #e8eaff;background:#ffffff;vertical-align:middle;">
                                                <span style="font-size:56px;font-weight:700;color:{color};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1;">{score}</span><br/>
                                                <span style="font-size:14px;color:#a0aec0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">/100</span>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            <tr>
                                <td align="center" style="padding-bottom:8px;">
                                    <table cellpadding="0" cellspacing="0" border="0">
                                        <tr>
                                            <td style="padding:6px 20px;border-radius:10px;background:{color}15;border:1px solid {color}40;">
                                                <span style="font-size:24px;font-weight:700;color:{color};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">{grade}</span>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            <tr><td align="center" style="font-size:11px;color:#a0aec0;padding-top:4px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Scored by <a href="https://gradeforai.com" style="color:#4353ff;text-decoration:none;font-weight:600;">GradeForAI</a></td></tr>
                        </table>
                    </td>
                </tr>

                <tr><td style="height:24px;"></td></tr>

                <!-- Dimensions -->
                <tr>
                    <td style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:24px;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr><td style="font-size:16px;font-weight:600;color:#1a202c;padding-bottom:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Your Dimensions</td></tr>
                            <tr>
                                <td>
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                        {dim_rows}
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <tr><td style="height:24px;"></td></tr>

                <!-- CTA -->
                <tr>
                    <td style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:28px;text-align:center;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr><td align="center" style="font-size:18px;font-weight:700;color:#1a202c;padding-bottom:8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Want the full breakdown?</td></tr>
                            <tr><td align="center" style="font-size:14px;color:#4a5568;padding-bottom:20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Get exactly what to fix, ranked by impact, with competitor benchmarks and a step-by-step implementation roadmap.</td></tr>
                            <tr>
                                <td align="center">
                                    <table cellpadding="0" cellspacing="0" border="0">
                                        <tr>
                                            <td style="background:#4353ff;border-radius:10px;padding:14px 36px;">
                                                <a href="https://gradeforai.com/results?id={{{{scan_id}}}}" style="color:#ffffff;font-weight:700;font-size:15px;text-decoration:none;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">View Full Results</a>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <tr><td style="height:24px;"></td></tr>

                <!-- Footer -->
                <tr>
                    <td style="text-align:center;padding-top:24px;border-top:1px solid #e2e8f0;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr><td align="center" style="font-size:12px;color:#a0aec0;padding-bottom:4px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"><a href="https://gradeforai.com" style="color:#a0aec0;text-decoration:none;">gradeforai.com</a></td></tr>
                            <tr><td align="center" style="font-size:11px;color:#cbd5e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">You received this because you scanned {domain} on GradeForAI.</td></tr>
                            <tr><td align="center" style="font-size:11px;color:#cbd5e0;padding-top:2px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Reply to this email to unsubscribe.</td></tr>
                        </table>
                    </td>
                </tr>

            </table>
        </td>
    </tr>
</table>
</body>
</html>"""


def _email_wrapper(content):
    """Wrap email content in standard GradeForAI email chrome."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#ffffff;">
    <tr>
        <td align="center" style="padding:32px 16px;">
            <table cellpadding="0" cellspacing="0" border="0" width="560" style="max-width:560px;width:100%;">
                <tr>
                    <td align="center" style="padding-bottom:32px;">
                        <a href="https://gradeforai.com" style="text-decoration:none;"><img src="https://gradeforai.com/assets/gradeforai-logo-email.png" alt="GradeForAI" width="180" style="display:block;margin:0 auto;border:0;" /></a>
                    </td>
                </tr>
                <tr><td>{content}</td></tr>
                <tr>
                    <td style="text-align:center;padding-top:24px;border-top:1px solid #e2e8f0;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr><td align="center" style="font-size:12px;color:#a0aec0;padding-bottom:4px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"><a href="https://gradeforai.com" style="color:#a0aec0;text-decoration:none;">gradeforai.com</a></td></tr>
                            <tr><td align="center" style="font-size:11px;color:#cbd5e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Reply to this email to unsubscribe.</td></tr>
                        </table>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>
</body>
</html>"""


# -- Nurture sequence templates (sent after free scan email capture) --

DIMENSION_EXPLANATIONS = {
    "Agent Accessibility": "AI agents cannot navigate your website effectively. Issues like aggressive bot-blocking, inaccessible forms, poor semantic HTML, or missing agent protocols prevent agents from operating on your site.",
    "Transaction Completeness": "There is no way for AI agents to complete the core transaction on your site. Whether it is booking, scheduling, quoting, or purchasing, agents cannot act on behalf of your customers.",
    "Data Reliability": "Your operational data is not structured for machine extraction, or the data agents extract may be stale or inconsistent. Service details, hours, pricing, location, and NAP consistency all need to be in formats that AI agents can reliably read and act on.",
    "Competitive Position": "Your AI agent readiness falls behind similar businesses in your area. Competitors are better positioned for agent-driven transactions, which means agents are more likely to operate through them instead of you.",
    # Legacy keys (for backward compat with older score data)
    "Agent Compatibility": "AI agents cannot navigate your website effectively. Issues like aggressive bot-blocking, inaccessible forms, or poor semantic HTML prevent agents from operating on your site.",
    "Transaction Readiness": "There is no way for AI agents to complete the core transaction on your site. Whether it is booking, scheduling, or purchasing, agents cannot act on behalf of your customers.",
    "Agentic Commerce Readiness": "Your site is not connected to emerging agent protocols. Standards like UCP, ACP, and agent.json let AI agents discover and interact with your business programmatically.",
    "Operational Data Structure": "Your operational data is not structured for machine extraction. Service details, hours, pricing, and location need to be in formats that AI agents can reliably read and act on.",
    "Data Accuracy & Currency": "The data agents extract from your site may be stale or inconsistent. Mismatched NAP info, outdated hours, or identity conflicts cause agents to route customers elsewhere.",
}


def nurture_email_2_html(domain, score, grade, weakest_dim, weakest_score):
    """Day 1: Educate on their weakest dimension."""
    explanation = DIMENSION_EXPLANATIONS.get(weakest_dim, "")
    content = f"""
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:28px;">
            <tr><td style="font-size:18px;font-weight:700;color:#1a202c;padding-bottom:16px;">Your biggest gap: {weakest_dim}</td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                Yesterday you scanned <strong>{domain}</strong> and scored <strong style="color:#e53e3e;">{score}/100</strong>.
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                Your lowest dimension was <strong>{weakest_dim}</strong> at <strong style="color:#e53e3e;">{weakest_score}/100</strong>.
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:20px;">
                Here is what that means in plain English: {explanation}
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:20px;">
                This is fixable. Many businesses can start improving this dimension quickly once they know what to focus on.
            </td></tr>
            <tr>
                <td align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td style="background:#4353ff;border-radius:10px;padding:14px 36px;">
                                <a href="https://gradeforai.com/results?url={domain}" style="color:#ffffff;font-weight:700;font-size:15px;text-decoration:none;">See Your Full Breakdown</a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>"""
    return _email_wrapper(content)


def nurture_email_3_html(domain, score, grade, vertical_avg):
    """Day 3: Competitive comparison."""
    diff = score - vertical_avg
    if diff < 0:
        comparison = f"Your score of <strong style='color:#e53e3e;'>{score}</strong> is <strong>{abs(int(diff))} points below</strong> the average in your industry ({int(vertical_avg)}/100)."
    else:
        comparison = f"Your score of <strong style='color:#22863a;'>{score}</strong> is <strong>{int(diff)} points above</strong> the average in your industry ({int(vertical_avg)}/100)."

    content = f"""
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:28px;">
            <tr><td style="font-size:18px;font-weight:700;color:#1a202c;padding-bottom:16px;">How you compare to your competitors</td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                We have scanned thousands of businesses across every major vertical. Here is where <strong>{domain}</strong> lands:
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                {comparison}
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                The businesses that are pulling ahead right now are the ones fixing their scores early. AI adoption is moving fast, and the gap between prepared and unprepared businesses continues to grow.
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:20px;">
                The full report shows exactly how you compare across all dimensions, plus the specific fixes that would move your score the most.
            </td></tr>
            <tr>
                <td align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td style="background:#4353ff;border-radius:10px;padding:14px 36px;">
                                <a href="https://gradeforai.com/results?url={domain}" style="color:#ffffff;font-weight:700;font-size:15px;text-decoration:none;">View Your Results</a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>"""
    return _email_wrapper(content)


def nurture_email_4_html(domain, score, grade):
    """Day 5: Value stack for the $199 report."""
    content = f"""
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:28px;">
            <tr><td style="font-size:18px;font-weight:700;color:#1a202c;padding-bottom:16px;">What the full report actually gives you</td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                Your free scan showed that <strong>{domain}</strong> scored <strong style="color:#e53e3e;">{score}/100</strong>. The free scan tells you the problem. The full report tells you exactly how to fix it.
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:4px;">Here is what is inside:</td></tr>
            <tr><td style="padding-bottom:16px;">
                <table cellpadding="0" cellspacing="0" border="0" style="margin-top:8px;">
                    <tr><td style="padding:5px 0;font-size:14px;color:#4a5568;">&#10003;&nbsp; Individual scores for all 4 dimensions</td></tr>
                    <tr><td style="padding:5px 0;font-size:14px;color:#4a5568;">&#10003;&nbsp; Exactly what to fix, ranked by impact on your score</td></tr>
                    <tr><td style="padding:5px 0;font-size:14px;color:#4a5568;">&#10003;&nbsp; How you compare to up to 3 competitors</td></tr>
                    <tr><td style="padding:5px 0;font-size:14px;color:#4a5568;">&#10003;&nbsp; Industry benchmark data across thousands of scored businesses</td></tr>
                    <tr><td style="padding:5px 0;font-size:14px;color:#4a5568;">&#10003;&nbsp; Step-by-step implementation roadmap</td></tr>
                    <tr><td style="padding:5px 0;font-size:14px;color:#4a5568;">&#10003;&nbsp; 30-day re-scan to measure your progress</td></tr>
                </table>
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:20px;">
                It is $199, one time. You can hand it to your web developer or work through it yourself. Either way, you will know exactly what to do and in what order.
            </td></tr>
            <tr>
                <td align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td style="background:#4353ff;border-radius:10px;padding:14px 36px;">
                                <a href="https://gradeforai.com/results?url={domain}" style="color:#ffffff;font-weight:700;font-size:15px;text-decoration:none;">Get Your Full Report - $199</a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding-top:12px;">
                    <span style="font-size:13px;color:#22863a;font-weight:600;">7-day money-back guarantee. No hoops.</span>
                </td>
            </tr>
        </table>"""
    return _email_wrapper(content)


def nurture_email_5_html(domain, score, grade):
    """Day 7: Final nudge."""
    content = f"""
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:28px;">
            <tr><td style="font-size:18px;font-weight:700;color:#1a202c;padding-bottom:16px;">Quick check-in on your AI readiness</td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                A week ago you scanned <strong>{domain}</strong> and scored <strong style="color:#e53e3e;">{score}/100</strong> ({grade}).
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                Just wanted to check in. AI adoption is accelerating and the businesses that act now will have a significant advantage over those that wait.
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:16px;">
                If you have any questions about your score or what the fixes involve, just reply to this email. I read every one.
            </td></tr>
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;padding-bottom:20px;">
                Or if you want the full breakdown with a step-by-step fix list, the report is still available.
            </td></tr>
            <tr>
                <td align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td style="background:#4353ff;border-radius:10px;padding:14px 36px;">
                                <a href="https://gradeforai.com/results?url={domain}" style="color:#ffffff;font-weight:700;font-size:15px;text-decoration:none;">View Your Results</a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:16px;">
            <tr><td style="font-size:14px;color:#4a5568;line-height:1.75;">
                <strong>Mark Laird</strong><br>
                GradeForAI
            </td></tr>
        </table>"""
    return _email_wrapper(content)


def report_purchased_email_html(domain, score, grade):
    """Email sent after Stripe purchase confirming report delivery."""
    color = _band_color(score)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#ffffff;">
    <tr>
        <td align="center" style="padding:32px 16px;">
            <table cellpadding="0" cellspacing="0" border="0" width="560" style="max-width:560px;width:100%;">

                <!-- Logo -->
                <tr>
                    <td align="center" style="padding-bottom:32px;">
                        <a href="https://gradeforai.com" style="text-decoration:none;"><img src="https://gradeforai.com/assets/gradeforai-logo-email.png" alt="GradeForAI" width="180" style="display:block;margin:0 auto;border:0;" /></a>
                    </td>
                </tr>

                <!-- Report Ready Card -->
                <tr>
                    <td style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:32px;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr><td align="center" style="font-size:24px;font-weight:700;color:#22863a;padding-bottom:8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Your Full Report is Ready</td></tr>
                            <tr><td align="center" style="font-size:14px;color:#a0aec0;padding-bottom:24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">{domain} scored <span style="color:{color};font-weight:700;">{score}/100</span> (<span style="color:{color};font-weight:700;">{grade}</span>)</td></tr>
                            <tr>
                                <td style="font-size:14px;color:#4a5568;line-height:1.8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
                                    Your AI Agent Preference Score Report is attached to this email. It includes:
                                    <table cellpadding="0" cellspacing="0" border="0" style="margin-top:12px;">
                                        <tr><td style="padding:4px 0;font-size:14px;color:#4a5568;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">&bull;&nbsp; Deep analysis of all 4 dimensions</td></tr>
                                        <tr><td style="padding:4px 0;font-size:14px;color:#4a5568;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">&bull;&nbsp; Prioritized action items ranked by impact</td></tr>
                                        <tr><td style="padding:4px 0;font-size:14px;color:#4a5568;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">&bull;&nbsp; Competitor benchmarks for your vertical</td></tr>
                                        <tr><td style="padding:4px 0;font-size:14px;color:#4a5568;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">&bull;&nbsp; Implementation guides with code snippets</td></tr>
                                        <tr><td style="padding:4px 0;font-size:14px;color:#4a5568;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">&bull;&nbsp; Schema.org templates ready to paste</td></tr>
                                        <tr><td style="padding:4px 0;font-size:14px;color:#4a5568;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">&bull;&nbsp; 30-day re-scan to measure your progress</td></tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <tr><td style="height:24px;"></td></tr>

                <!-- Implementation CTA -->
                <tr>
                    <td style="background:#f7f8fa;border:1px solid #e2e8f0;border-radius:16px;padding:24px;text-align:center;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr><td align="center" style="font-size:16px;font-weight:600;color:#1a202c;padding-bottom:8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Need help implementing?</td></tr>
                            <tr><td align="center" style="font-size:14px;color:#4a5568;padding-bottom:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">We can handle the technical implementation for you. Reach out to discuss your score and next steps.</td></tr>
                            <tr>
                                <td align="center">
                                    <table cellpadding="0" cellspacing="0" border="0">
                                        <tr>
                                            <td style="background:#4353ff;border-radius:10px;padding:12px 28px;">
                                                <a href="mailto:mark@gradeforai.com?subject=Implementation%20Help%20-%20{domain}" style="color:#ffffff;font-weight:700;font-size:14px;text-decoration:none;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Get Implementation Help</a>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <tr><td style="height:24px;"></td></tr>

                <!-- Footer -->
                <tr>
                    <td style="text-align:center;padding-top:24px;border-top:1px solid #e2e8f0;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            <tr><td align="center" style="font-size:12px;color:#a0aec0;padding-bottom:4px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"><a href="https://gradeforai.com" style="color:#a0aec0;text-decoration:none;">gradeforai.com</a></td></tr>
                            <tr><td align="center" style="font-size:11px;color:#cbd5e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Thank you for your purchase.</td></tr>
                        </table>
                    </td>
                </tr>

            </table>
        </td>
    </tr>
</table>
</body>
</html>"""
