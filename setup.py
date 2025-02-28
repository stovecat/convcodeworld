from setuptools import setup, find_packages

setup(
    name='convcodeworld',
    version='0.3.6',
    packages=find_packages(),  # Automatically find packages in your_project
    install_requires=[
        # Add your dependencies here
    ],
    author='Hojae Han',
    author_email='hojae.han@snowflake.com',
    description='Benchmarking Conversational Code Generation in Reproducible Environments',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/sfc-gh-hhan/convcodeworld',  # Project's homepage
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',  # Adjust as necessary
        'Operating System :: OS Independent',
    ],
    python_requires='==3.9.19',  # Specify your Python version requirement
)

