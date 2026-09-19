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

        dynamic_routes = []
        active_rides = Ride.objects.filter(status='active').order_by('-created_at')

        if active_rides.exists():
            grouped_routes = {}
            for ride in active_rides:
                orig_city = clean_city_name(ride.origin, ride.pickup_address)
                dest_city = clean_city_name(ride.destination, ride.drop_address)

                if orig_city == dest_city:
                    orig_disp = get_display_name(ride.origin, ride.pickup_address, orig_city)
                    dest_disp = get_display_name(ride.destination, ride.drop_address, dest_city)
                    if orig_disp != dest_disp:
                        origin_text = f"{orig_disp} ({orig_city})"
                        dest_text = f"{dest_disp}"
                    else:
                        origin_text = orig_city
                        dest_text = dest_city
                else:
                    origin_text = orig_city
                    dest_text = dest_city

                pair_key = (origin_text, dest_text)
                price = float(ride.price_per_seat)

                if pair_key not in grouped_routes:
                    grouped_routes[pair_key] = {
                        'origin': origin_text,
                        'destination': dest_text,
                        'search_origin': orig_city,
                        'search_dest': dest_city,
                        'min_price': price,
                        'count': 1
                    }
                else:
                    grouped_routes[pair_key]['count'] += 1
                    if price < grouped_routes[pair_key]['min_price']:
                        grouped_routes[pair_key]['min_price'] = price

            for key, data in list(grouped_routes.items())[:6]:
                dynamic_routes.append({
                    'origin': data['origin'],
                    'destination': data['destination'],
                    'search_origin': data['search_origin'],
                    'search_dest': data['search_dest'],
                    'min_price': int(data['min_price']) if data['min_price'] == int(data['min_price']) else data['min_price'],
                    'freq_text': f"{data['count']} active ride(s)"
                })
        else:
            default_routes = [
                {'origin': 'Delhi', 'destination': 'Jaipur', 'search_origin': 'Delhi', 'search_dest': 'Jaipur', 'min_price': 450, 'freq_text': 'Daily 15+ rides'},
                {'origin': 'Gurgaon', 'destination': 'Rohtak', 'search_origin': 'Gurgaon', 'search_dest': 'Rohtak', 'min_price': 150, 'freq_text': 'Daily 25+ rides'},
                {'origin': 'Mumbai', 'destination': 'Pune', 'search_origin': 'Mumbai', 'search_dest': 'Pune', 'min_price': 350, 'freq_text': 'Daily 30+ rides'},
                {'origin': 'Bangalore', 'destination': 'Mysore', 'search_origin': 'Bangalore', 'search_dest': 'Mysore', 'min_price': 300, 'freq_text': 'Daily 20+ rides'},
                {'origin': 'Jaipur', 'destination': 'Jodhpur', 'search_origin': 'Jaipur', 'search_dest': 'Jodhpur', 'min_price': 400, 'freq_text': 'Daily 12+ rides'},
                {'origin': 'Jaipur', 'destination': 'Alwar', 'search_origin': 'Jaipur', 'search_dest': 'Alwar', 'min_price': 250, 'freq_text': 'Daily 18+ rides'},
            ]
            dynamic_routes = default_routes[:6]

        context['popular_routes'] = dynamic_routes[:6]
        context['faqs'] = FAQ.objects.filter(is_published=True)[:6]

        try:
            context['recent_rides'] = (
                Ride.objects
                .filter(status='active')
                .order_by('-created_at')[:4]
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

        # Email Syntax & Format Validation
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        is_valid_email = True
        if email:
            try:
                validate_email(email)
            except ValidationError:
                is_valid_email = False

        from apps.admin_panel.models import ContactInquiry
        inquiry = ContactInquiry.objects.create(
            name=name or "Website Visitor",
            email=email or "Not Provided",
            phone=phone or "",
            category=category,
            subject=subject,
            message=message_text,
            is_email_valid=is_valid_email,
            status='NEW' if is_valid_email else 'INVALID_EMAIL'
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
            messages.success(request, f"🎉 Thank you {name or ''}! Your message has been sent to our Kaapool support team. We will get back to you shortly.")
        else:
            messages.warning(request, f"⚠️ Your message was received, but the email address '{email}' appears invalid. No confirmation email was sent.")

        return redirect('core:contact')




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
    messages.error(request, "⚠️ Your form session or security token expired. Please try submitting again.")
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('accounts:login')

