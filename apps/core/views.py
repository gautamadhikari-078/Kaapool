import re
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Min
from apps.rides.models import Ride
from apps.admin_panel.models import WebsiteContent, FAQ, Blog, Complaint

User = get_user_model()

KNOWN_CITIES = [
    'Jaipur', 'Delhi', 'New Delhi', 'Gurgaon', 'Gurugram', 'Noida', 'Rohtak', 'Faridabad',
    'Ghaziabad', 'Mumbai', 'Pune', 'Bangalore', 'Bengaluru', 'Mysore', 'Chennai', 'Pondicherry',
    'Puducherry', 'Hyderabad', 'Vijayawada', 'Ahmedabad', 'Surat', 'Vadodara', 'Jodhpur',
    'Alwar', 'Udaipur', 'Kota', 'Ajmer', 'Bikaner', 'Bhilwara', 'Chandigarh', 'Amritsar',
    'Ludhiana', 'Shimla', 'Dehradun', 'Agra', 'Kanpur', 'Lucknow', 'Varanasi', 'Prayagraj',
    'Kolkata', 'Patna', 'Ranchi', 'Indore', 'Bhopal', 'Nagpur', 'Goa'
]


def clean_city_name(val, full_addr=''):
    combined = f"{val or ''} {full_addr or ''}".strip()
    for city in KNOWN_CITIES:
        if re.search(r'\b' + re.escape(city) + r'\b', combined, re.IGNORECASE):
            return city
    parts = [p.strip() for p in str(val or '').split(',') if p.strip()]
    if parts:
        last = parts[-1]
        if last.lower() in ['india', 'rajasthan', 'haryana', 'punjab', 'maharashtra', 'karnataka', 'uttar pradesh', 'delhi']:
            if len(parts) > 1:
                return parts[-2].title()
        return last.title()
    return str(val or '').title()


def get_display_name(val, full_addr='', city=''):
    parts = [p.strip() for p in str(val or '').split(',') if p.strip()]
    if not parts:
        return city
    first = parts[0]
    if first.lower() != city.lower() and len(first) > 2:
        return first
    return city


class HomeView(TemplateView):
    """Homepage view with dynamic CMS content & popular carpool routes."""
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        cms_home = WebsiteContent.objects.filter(section='homepage').first()
        context['cms_home'] = cms_home

        meta = cms_home.meta_data if (cms_home and cms_home.meta_data) else {}
        context['stats_data'] = {
            'stat1_target': meta.get('stat1_target', 21),
            'stat1_prefix': meta.get('stat1_prefix', ''),
            'stat1_suffix': meta.get('stat1_suffix', 'L+'),
            'stat1_label': meta.get('stat1_label', 'Happy Commuters'),

            'stat2_target': meta.get('stat2_target', 180),
            'stat2_prefix': meta.get('stat2_prefix', ''),
            'stat2_suffix': meta.get('stat2_suffix', '+'),
            'stat2_label': meta.get('stat2_label', 'Cities Connected'),

            'stat3_target': meta.get('stat3_target', 9400),
            'stat3_prefix': meta.get('stat3_prefix', ''),
            'stat3_suffix': meta.get('stat3_suffix', ' t'),
            'stat3_label': meta.get('stat3_label', 'CO₂ Emissions Saved'),

            'stat4_target': meta.get('stat4_target', 41),
            'stat4_prefix': meta.get('stat4_prefix', '₹'),
            'stat4_suffix': meta.get('stat4_suffix', ' Cr+'),
            'stat4_label': meta.get('stat4_label', 'Member Cost Saved'),
        }

        from django.utils import timezone
        now = timezone.now()

        # Fetch upcoming active/scheduled rides
        upcoming_rides = list(Ride.objects.filter(
            departure_datetime__gte=now,
            status__in=['scheduled', 'active']
        ))

        # 3 Fixed Popular Route Cards as requested
        card_definitions = [
            {
                'title_origin': 'Jaipur',
                'title_dest': 'Delhi',
                'search_origin': 'Jaipur',
                'search_dest': 'Delhi',
                'default_price': 450,
                'match_fn': lambda o, d: (
                    ('jaipur' in o and 'delhi' in d) or ('delhi' in o and 'jaipur' in d)
                )
            },
            {
                'title_origin': 'Delhi',
                'title_dest': 'Noida',
                'search_origin': 'Delhi',
                'search_dest': 'Noida',
                'default_price': 150,
                'match_fn': lambda o, d: (
                    ('delhi' in o and 'noida' in d) or ('noida' in o and 'delhi' in d)
                )
            },
            {
                'title_origin': 'Uttarakhand',
                'title_dest': 'Delhi',
                'search_origin': 'Uttarakhand',
                'search_dest': 'Delhi',
                'default_price': 550,
                'match_fn': lambda o, d: (
                    (any(k in o for k in ['uttarakhand', 'dehradun', 'haridwar', 'rishikesh']) and 'delhi' in d) or
                    ('delhi' in o and any(k in d for k in ['uttarakhand', 'dehradun', 'haridwar', 'rishikesh']))
                )
            },
        ]

        popular_routes = []
        for card_def in card_definitions:
            matching_rides = []
            for ride in upcoming_rides:
                orig_str = f"{ride.origin or ''} {ride.pickup_address or ''}".lower()
                dest_str = f"{ride.destination or ''} {ride.drop_address or ''}".lower()
                if card_def['match_fn'](orig_str, dest_str):
                    matching_rides.append(ride)

            if matching_rides:
                count = len(matching_rides)
                prices = [float(r.price_per_seat) for r in matching_rides if r.price_per_seat is not None]
                min_price = min(prices) if prices else card_def['default_price']
                freq_text = f"{count} ride{'s' if count != 1 else ''} available"
            else:
                min_price = card_def['default_price']
                freq_text = "Available daily"

            if isinstance(min_price, float) and min_price.is_integer():
                min_price = int(min_price)

            popular_routes.append({
                'origin': card_def['title_origin'],
                'destination': card_def['title_dest'],
                'search_origin': card_def['search_origin'],
                'search_dest': card_def['search_dest'],
                'min_price': min_price,
                'freq_text': freq_text,
                'is_bidirectional': True,
            })

        context['popular_routes'] = popular_routes
        context['faqs'] = FAQ.objects.filter(is_published=True)[:6]

        try:
            context['recent_rides'] = (
                Ride.objects
                .filter(status__in=['scheduled', 'active'], departure_datetime__gte=now)
                .order_by('departure_datetime')[:4]
            )
        except Exception:
            context['recent_rides'] = []


        return context


class AboutView(TemplateView):
    """About Kaapool page view with CMS."""
    template_name = 'core/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cms'] = WebsiteContent.objects.filter(section='about').first()
        return context


class HowItWorksView(TemplateView):
    """How Kaapool works page view with CMS."""
    template_name = 'core/how_it_works.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cms'] = WebsiteContent.objects.filter(section='how_it_works').first()
        return context


class SafetyView(TemplateView):
    """Safety guidelines page view with CMS."""
    template_name = 'core/safety.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cms'] = WebsiteContent.objects.filter(section='safety').first()
        return context


class ContactView(View):
    """Contact page view with CMS and interactive message submission."""
    template_name = 'core/contact.html'

    def get(self, request, *args, **kwargs):
        cms = WebsiteContent.objects.filter(section='contact').first()
        faqs = FAQ.objects.filter(is_published=True)[:4]
        return render(request, self.template_name, {
            'cms': cms,
            'faqs': faqs
        })

    def post(self, request, *args, **kwargs):
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        category = request.POST.get('category', 'other')
        subject = request.POST.get('subject', '').strip() or f"Contact Inquiry from {name or 'Visitor'}"
        message_text = request.POST.get('message', '').strip()

        if not message_text:
            messages.error(request, "Please enter your message before sending.")
            return redirect('core:contact')

        word_count = len([w for w in message_text.split() if w])
        if word_count > 500:
            messages.error(request, f"Message limit exceeded! Your message contains {word_count} words. Maximum allowed is 500 words.")
            return redirect('core:contact')

        # Comprehensive Email Authenticity & Disposable Email Validation
        from apps.core.email_validator import validate_email_authenticity
        email_check = validate_email_authenticity(email)

        if not email_check['is_valid']:
            messages.error(request, email_check['reason'])
            return redirect('core:contact')

        is_valid_email = email_check['is_valid']

        from apps.admin_panel.models import ContactInquiry
        from django.utils import timezone

        existing_inquiries = list(ContactInquiry.objects.filter(email__iexact=email.strip()).order_by('-created_at')) if email else []

        if existing_inquiries:
            inquiry = existing_inquiries[0]
            combined_history = list(inquiry.reply_history or [])
            for inq in existing_inquiries:
                if inq.reply_history:
                    for item in inq.reply_history:
                        if not any(h.get('reply') == item.get('reply') and h.get('subject') == item.get('subject') for h in combined_history):
                            combined_history.append(item)
                if inq.admin_notes:
                    dt = inq.admin_replied_at or inq.created_at
                    if dt and timezone.is_aware(dt):
                        dt = timezone.localtime(dt)
                    entry = {
                        'subject': inq.subject,
                        'message': inq.message,
                        'reply': inq.admin_notes,
                        'replied_at': dt.strftime('%d %b %Y, %I:%M %p') if dt else ''
                    }
                    if not any(h.get('reply') == entry['reply'] and h.get('subject') == entry['subject'] for h in combined_history):
                        combined_history.append(entry)

            if len(existing_inquiries) > 1:
                dup_ids = [inq.id for inq in existing_inquiries[1:]]
                ContactInquiry.objects.filter(id__in=dup_ids).delete()

            inquiry.name = name or inquiry.name
            inquiry.phone = phone or inquiry.phone
            inquiry.category = category
            inquiry.subject = subject
            inquiry.message = message_text
            inquiry.is_email_valid = is_valid_email
            inquiry.status = 'NEW' if is_valid_email else 'INVALID_EMAIL'
            inquiry.admin_notes = ''
            inquiry.admin_replied_at = None
            inquiry.reply_history = combined_history
            inquiry.save()

            ContactInquiry.objects.filter(pk=inquiry.pk).update(
                name=inquiry.name,
                phone=inquiry.phone,
                category=category,
                subject=subject,
                message=message_text,
                is_email_valid=is_valid_email,
                status=inquiry.status,
                admin_notes='',
                admin_replied_at=None,
                reply_history=combined_history,
                created_at=timezone.now()
            )
        else:
            inquiry = ContactInquiry.objects.create(
                name=name or "Website Visitor",
                email=email or "Not Provided",
                phone=phone or "",
                category=category,
                subject=subject,
                message=message_text,
                is_email_valid=is_valid_email,
                status='NEW' if is_valid_email else 'INVALID_EMAIL',
                reply_history=[]
            )

        # Trigger emails ONLY if email is valid
        if is_valid_email and email:
            try:
                from apps.core.email_service import EmailService
                EmailService.send_contact_form_to_admin(
                    name=name or "Website Visitor",
                    sender_email=email,
                    phone=phone or "Not Provided",
                    category=category,
                    subject_text=subject,
                    message_text=message_text,
                    admin_email="gautamadhikari071@gmail.com"
                )

                class ContactTicket:
                    pass
                ticket = ContactTicket()
                ticket.name = name or "Valued Commuter"
                ticket.email = email
                ticket.subject = subject
                ticket.message = message_text
                EmailService.send_contact_us_ack(ticket)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Contact form email trigger error: {e}")

        if is_valid_email:
            messages.success(request, f"Thank you {name or ''}! Your message has been sent to our Kaapool support team. We will get back to you shortly.")
        else:
            messages.warning(request, f"Your message was received, but the email address '{email}' appears invalid. No confirmation email was sent.")

        return redirect('core:contact')


class ValidateEmailAPIView(View):
    """API view for real-time live email authentication and disposable check."""
    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse
        from apps.core.email_validator import validate_email_authenticity
        email = request.GET.get('email', '').strip()
        res = validate_email_authenticity(email)
        return JsonResponse(res)




class PublicFAQView(ListView):
    """Public FAQs page view."""
    template_name = 'core/faq.html'
    model = FAQ
    context_object_name = 'faqs'

    def get_queryset(self):
        return FAQ.objects.filter(is_published=True).order_by('display_order', '-created_at')


class PublicBlogListView(ListView):
    """Public Blogs listing page view."""
    template_name = 'core/blog_list.html'
    model = Blog
    context_object_name = 'blogs'
    paginate_by = 9

    def get_queryset(self):
        return Blog.objects.filter(is_published=True).order_by('-published_at', '-created_at')


class PublicBlogDetailView(DetailView):
    """Public Blog detail page view."""
    template_name = 'core/blog_detail.html'
    model = Blog
    context_object_name = 'blog'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Blog.objects.filter(is_published=True)


def custom_csrf_failure(request, reason=""):
    """Graceful custom CSRF failure handler to prevent raw yellow 403 error page."""
    from django.contrib import messages
    from django.shortcuts import redirect
    messages.error(request, "Your form session or security token expired. Please try submitting again.")
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('accounts:login')

