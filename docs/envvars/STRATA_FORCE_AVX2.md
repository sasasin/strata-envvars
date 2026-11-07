# `STRATA_FORCE_AVX2`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリ・vendor コピーの内部挙動は対象外。

## 役割

Strata の x86 CPU ISA probe に AVX-512 を利用不可と答えさせるテスト用フックです。実 CPU が AVX-512 対応でも、Strata の `cpu_avx512_ok()` / `cpu_avx512bw_ok()` 系の判定を下げ、対応する CPU カーネル選択を AVX2 などへ進ませます。AVX2 対応そのものを偽装する変数ではありません。

## 値と判定

Strata は文字列全体を parse せず、環境変数が存在し、先頭文字が `'1'` かだけを見ます。

| 値 | x86 の判定 |
|---|---|
| 未設定 | この変数による抑止なし。ISA 上限・CPU 機能・OS の状態を通常どおり調べる |
| 空文字 | 設定済みだが先頭文字は NUL のため抑止しない |
| `1`、`10`、`1anything` など | AVX-512 判定を false にする |
| `0`、`true`、` 1` など | この変数による抑止なし。通常の検査へ進む |

数値変換、空白除去、大文字小文字の変換、無効値警告はありません。値が `1` で始まっても AVX2 probe は別実装のままなので、AVX2 がない CPU に AVX2 を使わせることはありません。根拠: `src/kernels/cpu/expert_layout.cpp:75-78,114-117,206-238`。

## 有効になる条件

- x86 (`__x86_64__`, `__i386__`, `_M_X64`, `_M_IX86`) 用の probe と、その probe を呼ぶ Strata CPU カーネル経路で参照されます。非 x86 ビルドは同ファイルの非 x86 分岐で AVX-512 probe が常に false を返し、この環境変数を読みません（`src/kernels/cpu/expert_layout.cpp:42-50,74-80`）。
- Strata の x86 CPU カーネルがビルドに含まれる必要があります。`strata_kernels_cpu` は x86 と portable でソース構成を分け、AVX-512 命令を含む translation unit と baseline の probe を別々にコンパイルします（`CMakeLists.txt:2059-2076,2184-2194`）。
- AVX-512 を元々持たない CPU では、通常の CPUID / OS 状態検査も false になるため、この変数による選択差はありません。
- `STRATA_FORCE_ISA` の ISA 上限も AVX-512 利用条件です。`cpu_isa_free()` が `cpu_isa_cap() >= 3` を要求するため、そちらで上限を下げた場合も AVX-512 は無効です（`src/kernels/cpu/expert_layout.cpp:26-39,75-78`）。`STRATA_VNNI_TIER` は VNNI tier の一部条件を opt-in しますが、`STRATA_FORCE_AVX2` で `cpu_isa_free()` が false なら `cpu_vnni_ok()` 自体が false となり、tier を有効化しません（同:188-203）。
- canonical Q2_0 pack の起動要件確認 `cpu_features()` / `cpu_require_expert_support()` はこの環境変数を参照しません。したがって、この変数は AVX-512 を必要とする pack を AVX2 CPU で実行可能にする設定ではありません（同:424-448,451-463、`src/program/generate.cpp:4781-4802`）。

## 実行時の詳細

`cpu_avx512_ok()`、`cpu_avx512bw_ok()`、`cpu_vbmi_ok()`、`cpu_vnni_ok()` は各関数内の `static const` 判定を保持します。環境値は各 probe が初めて評価されるときに読み込まれ、結果はその probe ごとに cache されます。初回評価後にプロセス環境を変えても、その probe の結果は変わりません。`cpu_isa_free()` 自体は cache しませんが、呼び出し元の static 判定から一度だけ呼ばれます（`src/kernels/cpu/expert_layout.cpp:75-78,80-112,114-146,176-203`）。

値が有効（先頭が `1`）なら、対象 CPU が AVX-512 に対応している場合でも Strata の probe は AVX-512 を選びません。例えば native expert の i-quant gate/up は AVX-512 条件を落とし、形式・token 数・他設定が許せば AVX2 kernel を選択します。AVX2 kernel の無効化や CPU 非対応など条件に合わない場合は ggml-cpu 側の dot 経路へ進みます（`src/kernels/cpu/native_expert.cpp:454-471,489-505`）。Q2 行計算と activation quantizer の `*_any` dispatch も、AVX-512 条件が false なら AVX2、さらに未対応なら AVX1 の枝を選びます（`src/kernels/cpu/expert_layout.cpp:465-485`）。Trellis の dispatcher も AVX-512 probe を通して kernel tier を判定します（`src/kernels/cpu/tq_cpu.cpp:155-169`）。

この変数を直接表示するログ、警告、独自の終了経路はありません。native pack では probe 結果に応じて `strata generate: CPU expert kernels: AVX-2` などの stderr 表示があり得ます（`src/program/generate.cpp:4802-4808`）。canonical Q2_0 pack の AVX-512 必須チェックは別であり、非対応なら通常どおり診断を出して終了コード 1 となります（`src/kernels/cpu/expert_layout.cpp:451-463`）。AVX-512 と AVX2 では演算経路が変わります。実装コメントにも i-quant の丸め差に関する条件があるため、この設定による出力同一性や速度は一律には断定できません（`src/kernels/cpu/native_expert.cpp:480-485`）。`docs/DETAILS.md` にこの変数固有の仕様・測定値は見つかりませんでした。

全参照を検索した結果、実装上の読み取りは `src/kernels/cpu/expert_layout.cpp:76,116` のほか `src/dsv41/vendor/exl3_cpu.cpp:1030-1032` にあります。後者は vendor コピー内の読み取りとして調査範囲から除外し、その内部の tier 挙動は本書では Strata の一般的な挙動として説明しません。ほかにヘッダー・コメント・CMake の診断テスト用設定があり、`CMakeLists.txt:2882,2889` はテストプロセスに `STRATA_FORCE_AVX2=1` を渡しています。

## 根拠

- `src/kernels/cpu/expert_layout.cpp:42-50,75-78,80-146,176-203,206-238`: 対象 platform、値判定、AVX-512 probe の cache、AVX2 判定との独立性、他の ISA 条件。
- `src/kernels/cpu/expert_layout.cpp:424-463`: canonical pack の CPU 機能確認と失敗時の stderr / 終了。
- `src/kernels/cpu/native_expert.cpp:454-505`, `src/kernels/cpu/expert_layout.cpp:465-485`, `src/kernels/cpu/tq_cpu.cpp:155-169`: probe 結果を使う CPU kernel dispatch。
- `src/program/generate.cpp:4781-4808`: pack 種別ごとの起動確認と native pack の CPU kernel 表示。
- `CMakeLists.txt:2059-2076,2184-2194,2882,2889`: probe / kernel の build 構成と test からの値設定。
- `src/dsv41/vendor/exl3_cpu.cpp:1030-1032`: vendor コピー内の追加読み取り（挙動説明の根拠には不使用）。
