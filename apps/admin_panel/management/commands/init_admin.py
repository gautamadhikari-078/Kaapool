from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.admin_panel.models import WebsiteContent, FAQ, Blog

User = get_user_model()


class Command(BaseCommand):
    help = "Initializes default Super Admin role and populates initial dynamic CMS data."

    def handle(self, *args, **options):
        import os

        admin_username = os.getenv('DJANGO_SUPERUSER_USERNAME') or os.getenv('ADMIN_USERNAME') or 'admin'
        admin_email = os.getenv('DJANGO_SUPERUSER_EMAIL') or os.getenv('ADMIN_EMAIL') or 'admin@kaapool.com'
        admin_password = os.getenv('DJANGO_SUPERUSER_PASSWORD') or os.getenv('ADMIN_PASSWORD') or 'admin123'

        # 1. Create default superuser if none exists, or update password to admin123
        admin_user = User.objects.filter(username=admin_username).first() or User.objects.filter(email=admin_email).first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password
            )
            admin_user.role = 'super_admin'
            admin_user.email_verified = True
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"Created default Super Admin '{admin_username}' ({admin_email})."))
        else:
            admin_user.set_password(admin_password)
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.role = 'super_admin'
            admin_user.email_verified = True
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"Elevated user '{admin_user.username}' to 'super_admin' with updated password."))

        # 2. Automatically promote owner emails to super_admin
        owner_emails = ['gautamadhikari078@gmail.com', 'gautamadhikari071@gmail.com']
        custom_emails = [e.strip() for e in os.getenv('ADMIN_EMAILS', '').split(',') if e.strip()]
        all_owner_emails = set(owner_emails + custom_emails)

        for email_addr in all_owner_emails:
            for u in User.objects.filter(email__iexact=email_addr):
                if not u.is_superuser or not u.is_staff or u.role != 'super_admin':
                    u.is_superuser = True
                    u.is_staff = True
                    u.role = 'super_admin'
                    u.save()
                    self.stdout.write(self.style.SUCCESS(f"Promoted '{u.email}' ({u.username}) to 'super_admin'."))

        # 3. Ensure any other superusers have role='super_admin'
        for su in User.objects.filter(is_superuser=True):
            if su.role != 'super_admin':
                su.role = 'super_admin'
                su.save()

        # 2. Populate Website Content defaults if missing
        default_stats = {
            'stat1_target': 21,
            'stat1_prefix': '',
            'stat1_suffix': 'L+',
            'stat1_label': 'Happy Commuters',

            'stat2_target': 180,
            'stat2_prefix': '',
            'stat2_suffix': '+',
            'stat2_label': 'Cities Connected',

            'stat3_target': 9400,
            'stat3_prefix': '',
            'stat3_suffix': ' t',
            'stat3_label': 'CO₂ Emissions Saved',

            'stat4_target': 41,
            'stat4_prefix': '₹',
            'stat4_suffix': ' Cr+',
            'stat4_label': 'Member Cost Saved'
        }

        default_sections = [
            ('homepage', 'India\'s Most Trusted Intercity Carpooling', 'Travel together, save money, and make friends on every journey across India.', 'Welcome to Kaapool carpooling community.'),
            ('about', 'About Kaapool', 'Connecting travelers across Indian cities for safer, affordable, and sustainable rides.', 'Kaapool was built with a vision to revolutionize shared intercity mobility.'),
            ('contact', 'Get in Touch with Kaapool Support', 'We are here to assist you 24/7 with your bookings, driver verification, or ride safety.', 'Support email: support@kaapool.com | Toll-free: 1800-123-4567'),
            ('safety', 'Safety & Trust Guidelines', 'Your safety is our top priority. Every member passes verified ID checks.', 'We enforce 100% identity verification via Veriff & Sumsub, emergency assistance, and rated profiles.'),
            ('how_it_works', 'How Kaapool Works', 'Simple, reliable intercity carpooling in 3 easy steps.', 'Find a ride, book your seat, and travel comfortably with verified co-travelers.'),
            ('privacy_policy', 'Privacy Policy', 'We value your privacy and protect your personal data with high security encryption.', 'Our privacy practices comply with data protection regulations.'),
            ('terms_conditions', 'Terms & Conditions', 'General terms of service governing usage of Kaapool web platform.', 'By using Kaapool, you agree to adhere to community safety standards.'),
            ('cancellation_policy', 'Cancellation & Refund Policy', 'Clear, transparent rules for cancellations and instant refund processing.', 'Free cancellations up to 24 hours prior to departure time.'),
            ('refund_policy', 'Refund Guidelines', 'Automatic processing of eligible refunds back to source account.', 'Refunds are executed within 24-48 hours.')
        ]

        for code, title, subtitle, content in default_sections:
            defaults = {
                'title': title,
                'subtitle': subtitle,
                'content': content
            }
            if code == 'homepage':
                defaults['meta_data'] = default_stats

            obj, created = WebsiteContent.objects.get_or_create(
                section=code,
                defaults=defaults
            )
            if not created and code == 'homepage' and not obj.meta_data:
                obj.meta_data = default_stats
                obj.save()

        # 3. Populate sample FAQs if none exist
        if not FAQ.objects.exists():
            faqs_data = [
                ("How do I book a seat on a ride?", "Search your origin and destination, select a preferred ride schedule, click 'Book Seat', and confirm details.", "general", 1),
                ("How does driver verification work?", "Drivers submit government ID photos authenticated securely through Veriff / Sumsub verification before offering rides.", "drivers", 2),
                ("What if a driver cancels my ride?", "You will be notified immediately and receive an automatic 100% refund.", "passengers", 3),
                ("How are prices determined for rides?", "Ride costs are shared among co-travelers based on fuel and toll expenses.", "payments", 4),
            ]
            for q, a, cat, order in faqs_data:
                FAQ.objects.create(question=q, answer=a, category=cat, display_order=order, is_published=True)
            self.stdout.write(self.style.SUCCESS("Created initial default FAQs."))

        # 4. Populate sample Blog if none exist
        if not Blog.objects.exists():
            Blog.objects.create(
                title="Top 5 Tips for Safe and Comfortable Intercity Carpooling",
                slug="top-5-tips-safe-carpooling",
                category="safety",
                author_name="Kaapool Safety Team",
                content="<p>Carpooling is one of the most eco-friendly and cost-effective ways to travel across Indian cities. Here are top guidelines to ensure a smooth trip...</p>",
                excerpt="Essential safety tips and community guidelines for first-time carpoolers.",
                is_published=True,
                published_at=timezone.now()
            )
            self.stdout.write(self.style.SUCCESS("Created initial default blog post."))

        self.stdout.write(self.style.SUCCESS("Kaapool Super Admin initialization complete."))
