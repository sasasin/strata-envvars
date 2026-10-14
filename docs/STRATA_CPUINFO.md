# `STRATA_CPUINFO`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

コンテナの entrypoint が AVX2 対応状況を確認する CPU 情報ファイルのパスを指定します。主な用途は、実行ホストが AVX2 を報告していないときに警告を出すことです。Strata エンジンの ISA 選択、ビルド、設定ファイルには使われず、警告後も entrypoint は通常どおり続行します。ソース中のコメントはこの値をテスト用としています。

## 値と判定

| 値 | entrypoint の動作 |
|---|---|
| 未設定または空文字 | `/proc/cpuinfo` を調べる（POSIX shell の `${VAR:-default}` による） |
| 空でない文字列 | その文字列を CPU 情報ファイルのパスとして使う。値の形式、空白、大文字小文字は解析・正規化しない |
| 指定したファイルが読めない、または `^flags` に一致する行がない | AVX2 の警告を出さない |
| 最初に `^flags` に一致した行に単語 `avx2` がない | stderr に AVX2 不足の警告を3行出す |
| 最初に `^flags` に一致した行に単語 `avx2` がある | 警告を出さない |

`grep -q '^flags'` で少なくとも1行あることを確認し、`grep -m1 '^flags'` で最初の一致行だけを取り出して `grep -qw avx2` に渡します。従って複数の `flags` 行がある場合も2行目以降は判定に使いません。`avx2` は文字列全体との比較ではなく grep の単語一致です。

## 有効になる条件

この変数を読むのは `docker-entrypoint.sh` です。通常のコンテナ起動で使用される Dockerfile はこのスクリプトを `ENTRYPOINT` に指定しています（`Dockerfile:119`）。entrypoint が実行され、指定パスが読み取り可能で、ファイル中に `^flags` 行がある場合にだけ、内容によって警告判定ができます。

警告条件に合致しても終了・起動拒否・再ビルドはしません。出力は stderr に次の文言で行われ、その後のセットアップまたはサーバー起動に進みます。

```text
WARNING: this host CPU has no AVX2. The engine in this image is built for CPUs with AVX2, so it may stop
  with 'illegal instruction' (exit 132). Build the image on this machine (docker build), which compiles the
  engine for the CPU it runs on, and see docs/INSTALL.md (Older CPUs, experimental) for the older-CPU build.
```

## 実行時の詳細

変数は entrypoint 開始直後、`/opt/strata` への移動の後、他の設定環境変数の既定値を準備する前に一度だけ展開されます。実行中の変更を再読込する処理はありません。値はシェル変数 `cpuinfo` に代入され、`[ -r ... ]` と `grep` に渡されます。環境変数自体は書き換えられず、`cpuinfo` も export されません。

HEAD の tracked source を完全一致で検索したところ、環境変数としての読み取りは `docker-entrypoint.sh:12` のみでした。他の Strata プログラムがこの値を読む実装は確認できません。`setup.py` が `/proc/cpuinfo` を直接読む箇所はありますが、`STRATA_CPUINFO` を参照せず、この環境変数の指定値を利用しません。

## 根拠

- `docker-entrypoint.sh:9-17` — AVX2 不足時の警告の目的、既定ファイル、判定、警告文。警告だけで続行する制御フロー。
- `Dockerfile:67-71,119` — エンジンは Docker build 時にビルドされること、および entrypoint の指定。
- `docs/INSTALL.md:145-157` — 配布済みエンジンの AVX2 要件と、旧 CPU 向けの実験的ビルドに関する説明。文書は `STRATA_CPUINFO` 自体の設定方法を説明していません。

この判定は `/proc/cpuinfo` 互換の `flags` 行を想定しています。CPU 情報ファイルの形式が異なる場合、または仮想化環境などで内容がホストの実行能力を正しく表さない場合、警告が出ないか誤った警告になる可能性があります。実装コメントも flags file が VM で誤る可能性を挙げ、警告にとどめる理由としています。
