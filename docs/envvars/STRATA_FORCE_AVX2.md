# `STRATA_FORCE_AVX2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査開始時の Strata checkout は `## main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

## 役割

x86 CPU の実行時 ISA 判定で AVX-512 系の probe を不成立にし、AVX-512 カーネルの代わりに下位 ISA の経路を選ばせる開発・診断用 override です。`expert_layout.cpp` の `cpu_isa_free()` はこの変数が指定条件に合うと false を返し、AVX-512 機能の判定と VNNI 判定が AVX-512 を利用しない結果になります。`cpu_avx512bw_ok()` も同じ値条件で直接 false を返します（`engine/src/kernels/cpu/expert_layout.cpp:75-78,80-82,114-117,188-202`）。

これは「AVX2 を強制的に使えるようにする」変数ではありません。AVX2 probe の可否は CPU 機能と `STRATA_FORCE_ISA` の cap で別に決まり、この変数は `cpu_avx2_ok()` を変更しません（`engine/src/kernels/cpu/expert_layout.cpp:206-238`）。たとえば native expert の i-quant は AVX-512 が使えなければ AVX2、さらに AVX2 も使えなければ AVX1 または ggml-cpu の経路へ進みます（`engine/src/kernels/cpu/native_expert.cpp:568-584,696-704`）。CPU expert kernel は GPU backend の有無だけでなく CPU で expert を処理する経路にも関係します。

非 x86 ではこのファイルの x86 probe 実装ではなく、AVX 機能関数が false を返す別実装が使われます。この変数を読みません（`engine/src/kernels/cpu/expert_layout.cpp:42-50,74-78`）。

## 値と判定

両方の直接読み取り箇所は `std::getenv` の null 判定と `f[0] == '1'` を使います。文字列全体の比較や数値変換はしません。空文字は設定済みでも無効です。先頭文字が ASCII `1` なら後続文字を問わず有効です（`engine/src/kernels/cpu/expert_layout.cpp:75-77,114-117`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| x86 (`__x86_64__`, `__i386__`, `_M_X64`, `_M_IX86`) の runtime CPU probe | AVX-512 probe は通常の CPU/OS 機能判定へ進む | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `avx2` |
| 非 x86 | AVX-512 probe は元から false | 該当なし（読まれない） | 該当なし |

大文字小文字や空白を解釈する parser はありません。`'1'` 以外で始まる値は無効です。無効値について警告や fallback の専用処理はありません。

## 有効になる条件

- Strata の x86 CPU ISA probe を使うビルド・実行経路であること。この値は AVX-512 カーネルがコンパイル済みかどうかを変えず、runtime probe を通じて利用可否を決めます（`engine/src/kernels/cpu/expert_layout.cpp:42-50,74-117`）。
- `STRATA_FORCE_ISA` がある場合、`cpu_avx512_ok()` / `cpu_vnni_ok()` の dispatch 判定は `cpu_isa_cap() >= 3` も必要です。従って `STRATA_FORCE_ISA=avx2` / `avx` / `sse` は単独でも AVX-512 を抑止し、この変数との組み合わせでも AVX-512 は有効になりません。`STRATA_FORCE_ISA` の unset または空文字は cap 3 です（`engine/src/kernels/cpu/expert_layout.cpp:26-39,75-82`）。
- `STRATA_VNNI_TIER=1` は AVX-512 対応だが VBMI を持たない CPU で VNNI 経路を opt-in しますが、`STRATA_FORCE_AVX2` が有効なら `cpu_isa_free()` が先に false となるためこの VNNI 判定も false です（`engine/src/kernels/cpu/expert_layout.cpp:188-202`）。`docs/DETAILS.md:1274` も両変数を dispatch の cap と記しています。
- AVX2 自体が CPU/OS で利用可能であることは別途必要です。この変数で AVX2 非対応 CPU に AVX2 カーネルを実行させることはありません（`engine/src/kernels/cpu/expert_layout.cpp:206-238`）。
- Q2_0 canonical pack には専用の AVX-512 要件チェックがありますが、そのチェック `cpu_features()` はこの環境変数を読みません。したがってこの変数だけで canonical pack のサポート判定や拒否条件が変わるわけではありません（`engine/src/kernels/cpu/expert_layout.cpp:424-449,451-463`; `engine/src/program/generate.cpp:5598-5618`）。

## 実行時の詳細

直接の環境読み取りは `expert_layout.cpp` にある 2 箇所です。`cpu_isa_free()` は呼び出しごとに `getenv` しますが、主要な各 probe (`cpu_avx512_ok()`、`cpu_avx512bw_ok()`、`cpu_vnni_ok()`) は結果を関数内 `static const` に保存します。従って値は各 probe の初回評価時に実質固定され、同じプロセスで環境を変更しても評価済み probe の結果には反映されません。probe 間の初回評価時刻は同一とは限りません（`engine/src/kernels/cpu/expert_layout.cpp:75-82,80-112,114-146,188-204`）。

`cpu_avx512_ok()` が false になると、native expert の i-quant は `STRATA_NO_IQ512` が未設定でも AVX-512 kernel を選ばず、AVX2 対応かつ `STRATA_NO_IQ256` 未設定なら AVX2 に進みます。NVFP4 の 512-bit 経路も AVX2 対応なら 256-bit 経路へ進み、Q2_0 の行 kernel は VNNI-512 が使えないとき AVX2、さらに AVX2 がなければ AVX1 を選びます（`engine/src/kernels/cpu/native_expert.cpp:568-576,696-704,720-732`; `engine/src/kernels/cpu/expert_layout.cpp:465-485`）。`STRATA_NO_IQ256=1` など該当 kernel を止める別変数が設定されれば、その経路はさらに fallback します。

変数自体に CLI 引数・設定ファイルによる上書きはありません。実行エンジンのプロセス環境に設定して、関連 probe の初回評価より前に読ませる必要があります。サーバー専用の別読み取りやリクエスト単位の再評価は見つかりません。

## ログと測定値

この変数の有効・無効を直接知らせるログはありません。値が `1` で CPU が AVX2 対応なら、`generate.cpp` の native pack 起動時に `strata generate: CPU expert kernels: AVX-2` と出る経路があります。この表示は `cpu_vnni_ok()` が false のときに出し、AVX2 判定などで表示名を選びます（`engine/src/program/generate.cpp:5619-5634`）。canonical Q2_0 pack の実機 CPU 機能が不足すると別の AVX-512 要件案内を stderr に出して終了コード 1 となりますが、この拒否は `cpu_features()` の実機 probe によるもので、この変数がその probe を抑止するためではありません（`engine/src/program/generate.cpp:5598-5618`; `engine/src/kernels/cpu/expert_layout.cpp:424-449`）。

`docs/DETAILS.md:1274` は `STRATA_VNNI_TIER=1` の説明内で、この変数と `STRATA_FORCE_ISA` が dispatch を抑えると記載しています。ソース上も同じ関係です。同資料にこの変数単体の測定値はありません。

## 根拠

- `engine/src/kernels/cpu/expert_layout.cpp:26-39,42-50,75-146,188-238,424-463` — ISA cap、非 x86 実装、環境値判定、AVX-512/VNNI/AVX2 probe、canonical pack の CPU 機能判定。
- `engine/src/kernels/cpu/native_expert.cpp:568-584,696-704,720-732` — native expert kernel の優先順位と fallback。
- `engine/src/kernels/cpu/expert_layout.cpp:465-485` — Q2_0 行 kernel と activation quantizer の ISA fallback。
- `engine/src/program/generate.cpp:5598-5634` — canonical pack の要件案内、native pack の CPU kernel 起動表示。
- `docs/DETAILS.md:1274` — 関連する dispatch cap の記述。
