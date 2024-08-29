from collections import namedtuple
from unittest import IsolatedAsyncioTestCase, mock

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from app_utils.testing import NoSocketsTestCase

from package_monitor.core.distribution_packages import (
    DistributionPackage,
    compile_package_requirements,
    determine_system_python_version,
    gather_distribution_packages,
    gather_protected_packages_versions,
    is_marker_valid,
    is_version_in_specifiers,
    relevant_import_paths,
    to_version_or_none,
)
from package_monitor.tests.factories import (
    DistributionPackageFactory,
    MetadataDistributionStubFactory,
    PypiFactory,
    PypiReleaseFactory,
    make_packages,
)

MODULE_PATH = "package_monitor.core.distribution_packages"


SysVersionInfo = namedtuple("SysVersionInfo", ["major", "minor", "micro"])


class TestDistributionPackage(NoSocketsTestCase):
    @mock.patch(
        MODULE_PATH + ".metadata_helpers.identify_installed_django_apps", spec=True
    )
    def test_should_create_from_importlib_distribution(self, mock_identify_django_apps):
        # given
        dist = MetadataDistributionStubFactory(
            name="Alpha",
            version="1.2.3",
            requires=["bravo>=1.0.0"],
            files=["alpha/__init__.py"],
            homepage_url="https://www.alpha.com",
        )
        mock_identify_django_apps.return_value = ["alpha_app"]
        # when
        obj = DistributionPackage.create_from_metadata_distribution(dist)
        # then
        self.assertEqual(obj.name, "Alpha")
        self.assertEqual(obj.name_normalized, "alpha")
        self.assertEqual(obj.current, "1.2.3")
        self.assertEqual(obj.latest, "")
        self.assertListEqual([str(x) for x in obj.requirements], ["bravo>=1.0.0"])
        self.assertEqual(obj.apps, ["alpha_app"])
        self.assertEqual(obj.homepage_url, "")

    def test_should_not_be_outdated(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0", latest="1.0.0")
        # when/then
        self.assertFalse(obj.is_outdated())

    def test_should_be_outdated(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0", latest="1.1.0")
        # when/then
        self.assertTrue(obj.is_outdated())

    def test_should_return_none_as_outdated(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0", latest=None)
        # when/then
        self.assertIsNone(obj.is_outdated())

    def test_should_have_str(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0", latest=None)
        # when/then
        self.assertIsInstance(str(obj), str)

    def test_should_detect_as_prerelease(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0a1")
        # when/then
        self.assertTrue(obj.is_prerelease())

    def test_should_detect_not_as_prerelease(self):
        # given
        obj = DistributionPackageFactory(current="1.0.0")
        # when/then
        self.assertFalse(obj.is_prerelease())


class MyDist:
    @property
    def name(self):
        raise KeyError()

    @property
    def metadata(self):
        return {}


@mock.patch(MODULE_PATH + ".sys")
@mock.patch(MODULE_PATH + ".importlib_metadata.distributions", spec=True)
class TestFetchRelevantPackages(NoSocketsTestCase):
    def test_should_fetch_all_packages(self, mock_distributions, mock_sys):
        # given
        dist_alpha = MetadataDistributionStubFactory(name="alpha")
        dist_bravo = MetadataDistributionStubFactory(
            name="bravo", requires=["alpha>=1.0.0"]
        )
        mock_distributions.return_value = [dist_alpha, dist_bravo]
        mock_sys.path = []
        # when
        result = gather_distribution_packages()
        # then
        self.assertSetEqual({"alpha", "bravo"}, set(result.keys()))

    def test_should_ignore_corrupt_package(self, mock_distributions, mock_sys):
        dist_alpha = MetadataDistributionStubFactory(name="alpha")
        bad_dist = MyDist()
        mock_distributions.return_value = [bad_dist, dist_alpha]
        mock_sys.path = []
        # when
        result = gather_distribution_packages()
        # then
        self.assertSetEqual({"alpha"}, set(result.keys()))

    def test_should_filter_out_setuptools_vendor(self, mock_distributions, mock_sys):
        # given
        dist_alpha = MetadataDistributionStubFactory(name="alpha")
        mock_distributions.return_value = [dist_alpha]
        mock_sys.path = ["x/setuptools/_vendor", "path/to"]
        # when
        gather_distribution_packages()
        # then
        _, kwargs = mock_distributions.call_args
        self.assertNotIn("x/setuptools/_vendor", kwargs["path"])


class TestCompilePackageRequirements(NoSocketsTestCase):
    def test_should_compile_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        packages = make_packages(dist_alpha, dist_bravo)
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", []):
            result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_include_requirements_from_settings(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        packages = make_packages(dist_alpha, dist_bravo)
        # when
        with mock.patch(
            MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", ["alpha>2"]
        ):
            result = compile_package_requirements(packages)
        # then
        expected = {
            "alpha": {"bravo": SpecifierSet(">=1.0.0"), "CUSTOM": SpecifierSet(">2")}
        }
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_requirements_in_setting(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        packages = make_packages(dist_alpha, dist_bravo)
        # when
        with mock.patch(
            MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", ["alpha>2", "x!"]
        ):
            result = compile_package_requirements(packages)
        # then
        expected = {
            "alpha": {"bravo": SpecifierSet(">=1.0.0"), "CUSTOM": SpecifierSet(">2")}
        }
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        dist_charlie = DistributionPackageFactory(name="charlie", requires=["123"])
        packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", []):
            result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_ignore_python_version_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        dist_charlie = DistributionPackageFactory(
            name="charlie", requires=['alpha >= 1.0.0 ; python_version < "3.7"']
        )
        packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", []):
            result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)

    def test_should_ignore_invalid_extra_requirements(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha")
        dist_bravo = DistributionPackageFactory(name="bravo", requires=["alpha>=1.0.0"])
        dist_charlie = DistributionPackageFactory(
            name="charlie", requires=['alpha>=1.0.0; extra == "certs"']
        )
        packages = make_packages(dist_alpha, dist_bravo, dist_charlie)
        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_CUSTOM_REQUIREMENTS", []):
            result = compile_package_requirements(packages)
        # then
        expected = {"alpha": {"bravo": SpecifierSet(">=1.0.0")}}
        self.assertDictEqual(expected, result)


@mock.patch(MODULE_PATH + ".fetch_project_from_pypi_async")
class TestUpdatePackagesFromPyPi(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.python_version = determine_system_python_version()

    async def test_should_update_packages(self, mock_fetch_data_from_pypi_async):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        pypi_alpha.info.version = "1.1.0"
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={},
            system_python=self.python_version,
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.1.0")
        self.assertEqual(dist_alpha.homepage_url, "https://pypi.org/project/alpha/")

    async def test_should_ignore_prereleases_when_stable(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0a1"] = [PypiReleaseFactory()]
        pypi_alpha.info.version = "1.1.0a1"
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={},
            system_python=self.python_version,
        )

        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_include_prereleases_when_prerelease(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0a1")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.0.0a2"] = [PypiReleaseFactory()]
        pypi_alpha.info.version = "1.0.0a2"
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={},
            system_python=self.python_version,
        )

        # then
        self.assertEqual(dist_alpha.latest, "1.0.0a2")

    async def test_should_not_update_package_on_network_error(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        pypi_alpha.info.version = "1.1.0"
        mock_fetch_data_from_pypi_async.return_value = None
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={},
            system_python=self.python_version,
        )
        # then
        self.assertEqual(dist_alpha.latest, "")

    async def test_should_ignore_yanked_releases(self, mock_fetch_data_from_pypi_async):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(yanked=True)]
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={},
            system_python=self.python_version,
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_ignore_releases_with_incompatible_python_requirement(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(requires_python=">=3.7")]
        pypi_alpha.info.version = "1.1.0"
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={},
            system_python=Version("3.6.9"),
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_ignore_invalid_release_version(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["a3"] = [PypiReleaseFactory()]
        pypi_alpha.info.version = "a3"
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            system_python=self.python_version,
            protected_packages_versions={},
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_ignore_releases_not_matching_consolidated_requirements(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {"alpha": {"bravo": SpecifierSet("<=1.0.0")}}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        pypi_alpha.info.version = "1.1.0"
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            system_python=self.python_version,
            protected_packages_versions={},
        )
        # then
        self.assertEqual(dist_alpha.latest, "1.0.0")

    async def test_should_ignore_invalid_python_release_spec(
        self, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = make_packages(dist_alpha)
        requirements = {}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory(requires_python=">=3.4.*")]
        pypi_alpha.info.version = "1.1.0"
        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            system_python=self.python_version,
            protected_packages_versions={},
        )
        # then
        self.assertEqual(packages["alpha"].latest, "1.0.0")

    @mock.patch(MODULE_PATH + ".fetch_pypi_releases")
    async def test_should_ignore_updates_with_non_matching_requirements_1(
        self, mock_fetch_pypi_releases, mock_fetch_data_from_pypi_async
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {"bravo": {"alpha": SpecifierSet(">0.1.0")}}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.info.version = "1.2.0"
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        pypi_alpha.releases["1.2.0"] = [PypiReleaseFactory()]

        pypi_alpha_1 = PypiFactory(distribution=dist_alpha)
        pypi_alpha_1.info.version = "1.1.0"

        pypi_alpha_2 = PypiFactory(distribution=dist_alpha)
        pypi_alpha_2.info.version = "1.2.0"
        pypi_alpha_2.info.requires_dist = ["invalid>1>2", "Bravo>=1.0.0"]

        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        mock_fetch_pypi_releases.return_value = [
            pypi_alpha_1.asdict(),
            pypi_alpha_2.asdict(),
        ]

        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={"bravo": Version("0.5.0")},
            system_python=self.python_version,
        )

        # then
        self.assertEqual(dist_alpha.latest, "1.1.0")

    @mock.patch(MODULE_PATH + ".fetch_pypi_releases")
    async def test_should_ignore_updates_with_non_matching_requirements_2(
        self, mock_fetch_pypi_releases, mock_fetch_data_from_pypi_async
    ):
        """Bug #15"""
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {"bravo": {"alpha": SpecifierSet(">0.1.0")}}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.info.version = "1.2.0"
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        pypi_alpha.releases["1.2.0"] = [PypiReleaseFactory()]

        pypi_alpha_1 = PypiFactory(distribution=dist_alpha)
        pypi_alpha_1.info.version = "1.1.0"

        pypi_alpha_2 = PypiFactory(distribution=dist_alpha)
        pypi_alpha_2.info.version = "1.2.0"
        pypi_alpha_2.info.requires_dist = None

        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        mock_fetch_pypi_releases.return_value = [
            pypi_alpha_1.asdict(),
            pypi_alpha_2.asdict(),
        ]

        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={"bravo": Version("0.5.0")},
            system_python=self.python_version,
        )

        # then
        self.assertEqual(dist_alpha.latest, "1.2.0")

    @mock.patch(MODULE_PATH + ".fetch_pypi_releases")
    async def test_should_ignore_conflicting_dependencies_of_not_protected_packages_1(
        self, mock_fetch_pypi_releases, mock_fetch_data_from_pypi_async
    ):
        # given

        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {"bravo": {"alpha": SpecifierSet(">0.1.0")}}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.info.version = "1.2.0"
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        pypi_alpha.releases["1.2.0"] = [PypiReleaseFactory()]

        pypi_alpha_1 = PypiFactory(distribution=dist_alpha)
        pypi_alpha_1.info.version = "1.1.0"

        pypi_alpha_2 = PypiFactory(distribution=dist_alpha)
        pypi_alpha_2.info.version = "1.2.0"
        pypi_alpha_2.info.requires_dist = ["invalid>1>2", "Bravo>=1.0.0"]

        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        mock_fetch_pypi_releases.return_value = [
            pypi_alpha_1.asdict(),
            pypi_alpha_2.asdict(),
        ]

        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={},
            system_python=self.python_version,
        )

        # then
        self.assertEqual(dist_alpha.latest, "1.2.0")

    @mock.patch(MODULE_PATH + ".fetch_pypi_releases")
    async def test_should_ignore_dependencies_of_not_protected_packages_2(
        self, mock_fetch_pypi_releases, mock_fetch_data_from_pypi_async
    ):
        # given

        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        requirements = {"bravo": {"alpha": SpecifierSet(">0.1.0")}}
        pypi_alpha = PypiFactory(distribution=dist_alpha)
        pypi_alpha.info.version = "1.2.0"
        pypi_alpha.releases["1.1.0"] = [PypiReleaseFactory()]
        pypi_alpha.releases["1.2.0"] = [PypiReleaseFactory()]

        pypi_alpha_1 = PypiFactory(distribution=dist_alpha)
        pypi_alpha_1.info.version = "1.1.0"

        pypi_alpha_2 = PypiFactory(distribution=dist_alpha)
        pypi_alpha_2.info.version = "1.2.0"
        pypi_alpha_2.info.requires_dist = ["charlie>=1.0.0"]

        mock_fetch_data_from_pypi_async.return_value = pypi_alpha.asdict()
        mock_fetch_pypi_releases.return_value = [
            pypi_alpha_1.asdict(),
            pypi_alpha_2.asdict(),
        ]

        # when
        await dist_alpha.update_from_pypi_async(
            session=mock.MagicMock(),
            requirements=requirements,
            protected_packages_versions={"bravo": Version("0.5.0")},
            system_python=self.python_version,
        )

        # then
        self.assertEqual(dist_alpha.latest, "1.2.0")


class TestGatherProtectedPackagesVersions(NoSocketsTestCase):
    def test_should_return_protected_packages_with_versions(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        dist_bravo = DistributionPackageFactory(name="bravo", current="1.2.3")
        packages = {"alpha": dist_alpha, "bravo": dist_bravo}

        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_PROTECTED_PACKAGES", ["alpha"]):
            result = gather_protected_packages_versions(packages)

        # then
        self.assertDictEqual(result, {"alpha": Version("1.0.0")})

    def test_should_return_protected_packages_with_versions_and_non_canonical_names(
        self,
    ):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        dist_bravo = DistributionPackageFactory(name="bravo", current="1.2.3")
        packages = {"alpha": dist_alpha, "bravo": dist_bravo}

        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_PROTECTED_PACKAGES", ["Alpha"]):
            result = gather_protected_packages_versions(packages)

        # then
        self.assertDictEqual(result, {"alpha": Version("1.0.0")})

    def test_should_return_empty_when_no_protected_packages(self):
        # given
        dist_alpha = DistributionPackageFactory(name="alpha", current="1.0.0")
        packages = {"alpha": dist_alpha}

        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_PROTECTED_PACKAGES", []):
            result = gather_protected_packages_versions(packages)

        # then
        self.assertDictEqual(result, {})

    def test_should_return_empty_when_no_packages(self):
        # given
        packages = {}

        # when
        with mock.patch(MODULE_PATH + ".PACKAGE_MONITOR_PROTECTED_PACKAGES", ["alpha"]):
            result = gather_protected_packages_versions(packages)

        # then
        self.assertDictEqual(result, {})


class TestIsRequirementValid(NoSocketsTestCase):
    def test_should_report_correctly(self):
        cases = [
            ("alpha>1", True),
            ('alpha>1; python_version>"3.0"', True),
            ('alpha>1; python_version<"3.0"', False),
        ]
        for s, expected in cases:
            with self.subTest(case=s):
                r = Requirement(s)
                self.assertIs(is_marker_valid(r), expected)


class TestToVersionOrNone(NoSocketsTestCase):
    def test_should_report_correctly(self):
        cases = [
            ("1.0.0", Version("1.0.0")),
            ("invalid", None),
            ("1.0.0alpha1", None),
        ]
        for s, expected in cases:
            with self.subTest(case=s):
                self.assertEqual(to_version_or_none(s), expected)


class TestIsVersionInSpecifiers(NoSocketsTestCase):
    def test_should_report_correctly(self):
        cases = [
            (Version("1.0.0"), SpecifierSet(">=1.0.0"), True),
            (Version("0.1.0"), SpecifierSet(">=1.0.0"), False),
            (Version("0.1.0"), SpecifierSet(""), True),
        ]
        for v, s, expected in cases:
            with self.subTest(case=s):
                self.assertEqual(is_version_in_specifiers(v, s), expected)


class TestRelevantImportPaths(NoSocketsTestCase):
    @mock.patch(MODULE_PATH + ".EXCLUDED_IMPORT_PATHS", {"/path3"})
    @mock.patch(MODULE_PATH + ".sys.path", ["/path1/path2", "/path1/path3"])
    def test_x(self):
        x = relevant_import_paths()
        self.assertNotIn("/path3", x)
