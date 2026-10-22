# `STRATA_VERIFY_EARLY_PLE_FLAG`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

全 resident 用 speculative verify graph の起動前に、ホストが PLE（prompt lookup）用フラグを立てるタイミングを選びます。GPU graph の最初の wait kernel がこのフラグを待つため、HIP では最初の launch より先にフラグを上げるモードを既定にしています。CUDA と SYCL では既定値 0 で、従来の launch 後の処理順を使います。

この変数は `early_ple_flag_mode()` の `static const int` に保存され、最初に関数が呼ばれた時点で一度だけ読み取られます。その後プロセス内で環境を変更しても値は再評価されません。

## 値と判定

設定値は `std::atoi()` で整数化し、0〜2 に clamp します。文字列全体の妥当性検査はありません。

| 環境変数の状態 | HIP build | HIP 以外の build |
|---|---:|---:|
| unset | 2 | 0 |
| 数値化した値が 0 以下 | 0 | 0 |
| 数値化した値が 1 | 1 | 1 |
| 数値化した値が 2 以上 | 2 | 2 |

空文字や先頭が数値でない文字列は `atoi()` により 0 になります。数値の後ろに文字が続いても、先頭部分が整数として読めればその値を使います（例: `1junk` は 1）。負値は 0、2 を超える値は 2 になります。空白や符号などの扱いも `atoi()` の変換規則に従います。

モードの意味は次のとおりです。

- `0`: launch 前にはフラグを立てない。
- `1`: 対象となる各 window graph launch の前にフラグを立てる。
- `2`: 各 graph の初回 launch の前だけフラグを立てる。

根拠: `src/core/verify.cpp:272-289`。

## 有効になる条件

モード値だけでは動作は変わりません。`Verifier::run()` 内で、window が既に prelaunch 済みでないこと、all-resident (`ar_on()`) 経路であること、テスト用 stall window でないことが必要です。加えて、モード 1 または、モード 2 で当該 graph がまだ launch されていない場合に、launch 前の処理に入ります。`ar_on()` は `all_resident_ && !ar_off_` です。

このため、非 all-resident 経路、prelaunch 済み window、テスト stall window では、設定値が 1 または 2 でもこの launch 前処理は行われません。`do_ple` が偽でも条件を満たせばフラグ自体は launch 前に立てますが、PLE 行の収集は行いません。

根拠: `include/strata/core/verify.hpp:461`, `src/core/verify.cpp:2741-2742,2755-2768`。

## 実行時の詳細

launch 前処理が選ばれ、PLE が ready かつ対象 stage なら、`gather_batch()` で window の PLE 行を host staging 領域へ集め、メモリ fence を実行してから `h_flag_` を 1 にします。その後 graph を launch します。PLE 行を収集しない場合も、同じ位置でフラグを立てます。

launch 前処理に入らない経路では、通常の all-resident 処理が graph launch 後に PLE 行を収集してからフラグを立てます。フラグを launch 前に立てた場合は `flag_raised` により後段の重複した収集・flag raise を避けます。

根拠: `src/core/verify.cpp:2756-2768,2789-2794,2831-2843`。

## 文書との照合

リポジトリの `docs/release-notes-0.2.2.md:47` は、HIP の初回 graph launch で host が flag を launch 後に上げると hang することがあり、`=1` または `=0` で順序を強制できると説明しています。ソースでは中間値 `2` も実装され、HIP 既定値は 2（各 graph の初回だけ先行）、それ以外の build の既定値は 0 です。同リリースノートの再現回数や速度値はリリースノートに記載された測定であり、本調査で再測定したものではありません。

## 根拠

- `src/core/verify.cpp:272-289` — モードの定義、既定値、環境変数の parse と static cache。
- `include/strata/core/verify.hpp:461,533` — all-resident 判定と graph ごとの launch 済み状態。
- `src/core/verify.cpp:2741-2768,2789-2794,2831-2843` — PLE 行の収集、launch 前後の flag raise と graph launch。
- `docs/release-notes-0.2.2.md:47` — 変更理由とリリースノート上の測定記載。
