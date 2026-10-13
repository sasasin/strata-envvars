# `STRATA_GDN_HEAD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP の prompt prefill にある gated-delta-net（GDN）再帰計算で、AMD 向け quad/head カーネルとその出力 norm カーネルを選ぶスイッチ。quad カーネルは列ごとに4レーンを使う再帰カーネルで、再帰後は grid-stride の norm カーネルを使う。通常の GDN 計算全体を有効・無効にする変数ではない。

## 値と判定

| 状態 | 判定と結果 |
|---|---|
| 未設定 | カーネル側で `false`。ただし後述の gfx1151 / gfx12 の起動時既定値が適用される場合は `1` が設定される。 |
| 設定あり | `std::atoi(value) != 0` なら有効。空文字、数字に変換できない文字列、`0` で始まる数値は無効。`atoi` のため文字列全体の厳密な数値検証はせず、数値部分の後ろは判定に使わない（例: `2abc` は有効、`0abc` は無効）。負の非ゼロ値も有効。 |
| 明示的な `0` | 無効。gfx の起動時既定値処理も「変数が設定済み」とみなし、上書きしない。 |

起動時既定値の抑止用 `STRATA_GFX1151_DEFAULTS` / `STRATA_GFX12_DEFAULTS` は別の判定規則で、値の先頭文字が `0` のとき該当する既定値表を止める。それ以外の値（空文字を含む）では止めない。

## 有効になる条件

- `STRATA_USE_HIP` ビルドの `strata generate` は、GPU 0 の arch 名を取得できた場合、エンジンのスイッチ初回読み取り前に arch 既定値を適用する。gfx1151 では `STRATA_GFX1151_DEFAULTS` が先頭 `0` でなければ、gfx1200 / gfx1201 では `STRATA_GFX12_DEFAULTS` が先頭 `0` でなければ、それぞれ既定値 `STRATA_GDN_HEAD=1` を設定する。ユーザー環境に `STRATA_GDN_HEAD` が存在すれば、その値は空文字を含め上書きされない。その他の arch ではこの表から既定値は設定されない。ソースには gfx12 に対してもこの既定値がある一方、Strix Halo の説明文書は gfx1151 での既定有効化を記述している。
- GDN 再帰の呼び出しで `STRATA_GDN_REC_HEADS` が設定されていると、値に関係なく `STRATA_GDN_HEAD` の選択は打ち消され、従来の one-block-per-head 経路へ進む。
- `STRATA_GDN_HEAD` が有効でも quad 経路を実行するのは HIP の実装。CUDA 共通ソースにも環境値の読み取りはあるが、quad variant は HIP コンパイル時だけ実装され、CUDA 側では variant が無視されて従来経路を使う。SYCL の `kernels.dp.cpp` にも同じ値の読み取りがあるが、そのファイルで quad variant の処理は `__HIPCC__` 条件内にあり、非 HIPCC 側では variant を無視する。

## 実行時の詳細

1. HIP の起動処理が GPU 0 の arch に応じて既定値表を適用する。gfx1151 と gfx12 の表では他のスイッチも設定されるため、表から1個以上の値を設定した場合、stderr に `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...` または `strata: gfx12 (RDNA4): ...` の行が出て、設定したスイッチ名が並ぶ。明示設定済みの `STRATA_GDN_HEAD` はこの一覧の「設定した値」には含まれない。
2. prompt prefill が通常の GDN 層を処理するとき `gdn_recurrence()` を呼ぶ。初回呼び出し時に `STRATA_GDN_HEAD` と `STRATA_GDN_REC_HEADS` を function-local `static` として読み、その後の呼び出しでは同じ値を使う。このためプロセス起動後の環境変更は反映されない。
3. HIP で head が有効かつ `STRATA_GDN_REC_HEADS` が未設定なら variant 1 を選び、quad recurrence kernel と grid-stride output norm kernel を起動する。`STRATA_GDN_PP` が `atoi` で `2` なら二列処理版、それ以外の非ゼロなら別の PP 版、未設定・0相当なら基本 quad 版を選ぶ。`STRATA_GDN_NOY` も norm カーネルのテンプレート選択に関与する。
4. head が無効なら variant 0 となり、通常の列分割再帰またはソフトウェア pipeline 再帰と、通常の output norm を使う。どちらの通常再帰かは `STRATA_GDN_PIPELINE` などで選ばれる。`STRATA_GDN_REC_HEADS` 設定時は one-block-per-head カーネルへ進む。

GDN 再帰自体は通常の GDN 層の prompt prefill で呼ばれ、QSA 層の分岐では呼ばれない。ソースコメントと `docs/STRIX_HALO.md` は gfx1151 の当該経路について、既存経路と同じ結果を得る速度スイッチとして説明している。この調査では性能値を独自に検証していない。

## 根拠

- `src/core/arch_defaults.cpp:12-58` — gfx12（gfx1200 / gfx1201）および gfx1151 の既定値表、既定値無効化の先頭文字判定。
- `src/core/arch_defaults.cpp:61-80` — 環境変数が存在する場合は値を問わず保持し、未設定ならプロセス環境に既定値を設定する処理と stderr 出力。
- `src/program/generate.cpp:2152-2158`、`sycl/src/program/generate.cpp:1970-1976` — HIP 定義時、GPU 0 の arch 取得後に既定値表を適用する箇所。
- `src/prefill/prefill.cpp:2603-2626`、`sycl/src/prefill/prefill.cpp:2880-2910` — GDN 層の prompt prefill から `gdn_recurrence()` を呼ぶ箇所。前者では QSA 層を除外している。
- `src/prefill/kernels.cu:1065-1078` — HIP 専用 quad recurrence の構造と古いカーネルに関するコメント。
- `src/prefill/kernels.cu:1436-1460` — quad recurrence の後段で使う output norm が行を grid-stride で処理する実装。
- `src/prefill/kernels.cu:1927-2003` — variant の選択、`STRATA_GDN_HEAD` の `atoi` と static cache、`STRATA_GDN_REC_HEADS` による抑止、CUDA 側で variant を無視する条件。
- `src/prefill/kernels.cu:1951-1969` — variant 1 が選ぶ quad カーネル、PP / norm 系スイッチ。
- `sycl/src/prefill/kernels.dp.cpp:2603-2743` — SYCL 版にもある variant 分岐と `STRATA_GDN_HEAD` 読み取り。quad variant の処理は `__HIPCC__` 条件に置かれている。
- `docs/STRIX_HALO.md:85-93` — gfx1151 の既定値と GDN prompt recurrence スイッチの説明。
