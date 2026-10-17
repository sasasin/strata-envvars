# `STRATA_FILE_CACHE_OLD_RULE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Linux の `--mmap-experts` と resident budget を使う file expert tier が、expert ファイルの読み出しに OS file cache を使えるか判定する規則を選びます。旧規則は読み出す expert 全量がキャッシュに収まる場合だけ file cache を選びます。現行規則は余裕 RAM の一部を他の用途に残しつつ、読み出し対象の一部がキャッシュに残る場合も file cache を選びます。キャッシュに収まらない判定なら Strata は expert file を `O_DIRECT` で開こうとします。

## 値と判定

Linux の `src/core/expert_source.cpp` で、環境変数が未設定か空文字なら値による上書きをしません。空でない場合は先頭文字だけを見て、`'0'` なら旧規則を無効、その他の文字なら有効にします。数値変換や文字列全体の比較はありません。

| 値 | 規則の指定 |
|---|---|
| 未設定 / 空文字 | ビルド既定を使う。通常は現行規則、`STRATA_HIP_GFX906` ビルドでは旧規則 |
| `0` で始まる値（例: `0`, `0abc`） | 旧規則を無効にし、現行規則を選ぶ |
| `0` 以外で始まる非空値（例: `1`, `true`, `false`, `2abc`） | 旧規則を有効にする |

大文字小文字、先頭文字より後ろの内容、数値としての妥当性は判定しません。そのため `false` は旧規則を有効にし、`0false` は無効にします。gfx906 既定を環境変数で無効化する場合は、空文字ではなく `0` で始まる値を指定します。

## 有効になる条件

- 変数を読む実装は Linux の通常 `src/core/expert_source.cpp` にあります。Windows の分岐では `experts_unbuffered()` を使い、この変数を読みません。
- Linux でも、`--mmap-experts` が選ばれ、`--resident-budget-gib` 相当の resident budget が正であり、file tier の buffered / unbuffered 判定が実行される経路でのみ参照されます。resident budget がない場合、通常の expert cache が file tier を担い、この変数による判定は呼ばれません。
- `STRATA_HIP_GFX906` はビルド時に旧規則を既定にします。環境変数が非空なら、その指定がビルド既定を上書きします。定義の設定は `CMakeLists.txt` の `STRATA_HIP_GFX906` オプションによります。
- SYCL の複製実装 `sycl/src/core/expert_source.cpp` にはこの変数の読み取りがありません。そこでは `file_cache_keeps()` の既定引数を使うため、この環境変数による切替は行われません。
- Linux では別変数 `STRATA_UNBUFFERED_LOAD` が非空で設定されると、先にその先頭文字で buffered / unbuffered を決め、この変数によるルール選択をしません。`STRATA_UNBUFFERED_LOAD` の先頭が `0` なら buffered、それ以外なら unbuffered です。空文字はこの上書きを発動しません。

## 実行時の詳細

最初の判定は resident budget を使った `FileExpertSource::set_unbuffered()` から行われます。読み取る expert 数は全 expert bytes から RAM copy に入る分を除いたものです。resident RAM copy の構築後、起動時の unbuffered read が保持されなかった場合は `recheck_unbuffered()` が改めて判定し、実際の complement サイズから読み出し対象を再計算します。この環境変数は関数呼び出しごとに取得され、static cache されません。

旧規則は `file_cache_keeps(avail, arena_bytes, read_bytes)` の既定値を使い、他用途向け margin を 4 GiB、cache 対象を読み出し bytes の全量とします。現行規則は margin 1 GiB、hot fraction 0.05、floor 1.5 GiB を指定します。helper は `room = max(avail - arena_bytes - margin, 0)` を計算し、旧規則では `room >= read_bytes`、現行規則では `room >= min(read_bytes, max(0.05 * read_bytes, 1.5 GiB))` を cache 可能とします。利用可能 RAM の取得に失敗すると unbuffered を選ばず、理由に `the available RAM is unknown` を設定します。

cache 可能なら mmap 経由の file cache を使います。cache 不可なら Linux の `O_DIRECT` でファイルを開きますが、open に失敗すると Strata は直接読み取り descriptor を閉じ、file cache 経由に戻します。起動時と再判定時には stderr に `strata generate: the file tier reads ...` の結果と理由が出ます。環境変数の値そのものをこの判定ログへ出す処理はありません。

## 根拠

- `src/core/expert_source.cpp:508-553` — Linux 限定の判定、gfx906 既定、先頭文字による override、cache 可否から unbuffered 判定への反転。
- `include/strata/platform/memory.hpp:42-60` — 旧規則の既定引数（4 GiB margin、全量）と現行規則で使う計算式。
- `src/core/expert_source.cpp:1636-1652,1681-1697,1700-1725` — Linux `O_DIRECT` open と失敗時 fallback、初回判定および resident copy 後の再判定。
- `src/program/generate.cpp:5403-5434,7772-7782` — mmap expert tier の起動時呼び出しと resident copy 後の再判定条件・ログ。
- `CMakeLists.txt:64-67,137-152` — `STRATA_HIP_GFX906` build option と compile definition。
- `sycl/src/core/expert_source.cpp:384-412` — SYCL 側の複製には同名環境変数判定がなく、共通 helper の既定規則だけを使う。
- `docs/AMD_HIP.md:611` — gfx906 の既定と環境変数による旧・現行規則の切替についての既存説明。判定条件と値の細部は上記実装を根拠とした。
