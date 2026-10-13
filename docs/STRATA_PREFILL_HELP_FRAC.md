# `STRATA_PREFILL_HELP_FRAC`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_PREFILL_HELP=1` で有効にする layer split の prompt helper が、各 stage の非 resident expert のうち、helper 側 GPU へ渡して計算する share を指定します。`f` は 0〜1 に clamp され、各 stage の prompt path が別 stage の GPU に expert を送り、計算した行を受け取ります。unset の場合は chunk token 数 `T` に応じた自動 share です。

CUDA 実装と SYCL 実装に同じ判定式があります。通常の `--peer-device` 用 share とは別の経路で、この変数は layer split の helper share にだけ使われます（`src/prefill/prefill.cpp:1526-1541,1584-1590`; `sycl/src/prefill/prefill.cpp:1513-1528,1602-1608`）。

## 値と判定

値は `std::atof()` で変換し、その結果を `std::clamp(value, 0.0, 1.0)` に渡します。数値文字列全体の厳密な検証やエラー報告はありません。`atof` が認識した数値部分より後ろは値の判定に使われません。

| 値 | 判定 |
|---|---|
| unset | `fixed=-1.0`。chunk サイズに応じた自動 share を使用 |
| 空文字、数値に変換できない文字列 | `atof` の結果 0。share 0 で helper を使わない |
| 0 以下の数値（負値を含む） | 0 に clamp。helper を使わない |
| 0〜1 の数値 | その値を固定 share として使う。0 は無効、正値は候補になる |
| 1 より大きい数値 | 1 に clamp。対象となる pinned expert をすべて helper 側へ回す割合 |
| `atof` が NaN を返す入力 | `std::clamp` の結果も NaN となり、`fixed >= 0.0` が偽になるため自動 share に進む |

たとえば `0.25junk` は通常 `0.25` として扱われ、`-0.2` は 0、`2` は 1 です。変換結果は `split_help_frac()` 内の `static const double` に初回呼び出し時点で保存されるため、同じプロセスで環境を後から変更しても再読込されません。自動値も同じ static 初期化で固定されます。

unset 時の式は `f = min(0.45, 0.5 - T / 16384.0)` で、`f >= 0.3` のとき `f`、それより小さいとき 0 です。したがって通常の `T >= 1024` の範囲では 1024 token で 0.4375、3276 token で約 0.30005、3277 token から 0 です。`STRATA_PREFILL_STREAM_MIN` などが下限を変えた場合も、この式自体は同じです。

根拠: `src/prefill/prefill.cpp:1532-1541`; `sycl/src/prefill/prefill.cpp:1519-1528`。

## 有効になる条件

この値は単独では helper を有効にしません。少なくとも次の条件があります。

- 別変数 `STRATA_PREFILL_HELP` が `std::atoi()` で非 0 になり、layer split の stage helper が設定されていること。`STRATA_PREFILL_HELP` が unset、空、または数値変換結果 0 の場合は helper 自体が設定されません。
- 複数 GPU の layer split があること。serve 起動経路は multi-GPU かつ追加 stage がある場合、各 stage に次の stage の `Prefill` を helper として設定します。
- prompt が一つの chunk に収まること。各 stage の `run` は `single_chunk` のときだけ `bind_stage_helper()` を呼びます。
- chunk の `T` が `stream_all_min()` 以上であり、通常の既定値は 1024 token。stream ring が `STAGE`（8）より大きく、expert source があり、fused ring ではないこと。
- MMQ prompt 経路を使えること。全 stage の対象 layer が MMQ plan に含まれ、native pack で fused kernel が対応可能な layer がないこと。
- 既存の `--peer-device` helper がないこと。既存 peer がある場合は `m.pp` が設定済みとなり、stage helper の bind は拒否されます。
- helper stage に対象 chunk 分の初期化済み prompt buffer、MMQ context、stream ring があること。

このため、固定値を指定しても複数 chunk の prompt、短すぎる chunk、fused prompt 経路などでは使われません。固定値は自動 share の token 数 cutoff（約3.3K token）を変えますが、`bind_stage_helper()` 側の上記条件は残ります。

根拠: `src/program/generate.cpp:7375-7386`; `src/prefill/prefill.cpp:1544-1549,1584-1600,2083-2088,2301-2303`; SYCL 対応箇所 `sycl/src/program/generate.cpp:6948-6959`, `sycl/src/prefill/prefill.cpp:1531-1536,1602-1618,2463-2465`。

## 実行時の詳細

serve 起動時に各 layer stage の `set_stage_helper()` が呼ばれ、`STRATA_PREFILL_HELP` が有効なら helper 用の stream/event と参照先 buffer を設定します。`STRATA_PREFILL_HELP_FRAC` 自体はこの初期化時ではなく、single-chunk prompt の `bind_stage_helper(T)` で `split_help_frac(T)` が初めて呼ばれた時に読み込まれます。

bind が成功すると share は peer state の `ps_frac` に保存されます。stream-all の expert 列挙中、すでに resident / peer-owned の expert、transient source の expert は share の抽選対象になりません。安定した blob のうち source が pinned と判定した expert ごとに累積値へ `ps_frac` を加え、累積値が 1 以上になるたびにその expert を helper の ring に送り、累積値から 1 を引きます。従って小数 share は expert ごとの確率乱数ではなく、列挙順に沿った累積選択です。非 pinned expert は通常の stager 経路に残ります。

値を無効にした場合にこの変数固有の警告はありません。prompt timing が有効な場合、peer 側 timing 出力に helper で計算した expert 数が `strata prefill timing: peer-streamed experts ...` として表示されます。初期化時の一般的な peer 設定ログは通常の `--peer-device` 向けで、layer split helper の share を直接報告するログではありません。

根拠: `src/prefill/prefill.cpp:1586-1624,2083-2100,2313-2315,2342-2380,4183-4189`; SYCL 対応箇所 `sycl/src/prefill/prefill.cpp:1604-1642,2463-2466,2519-2560`。

## 文書との照合

`docs/MULTI_GPU.md:85-98` は、この変数が `STRATA_PREFILL_HELP=1` の helper 経路で固定 share を設定すると説明しています。また、2x RTX 3090、UD-Q4_K_XL、P2P なしでの測定として、share が prompt サイズとともに下が約3.3K token から自動で無効になること、固定 share の測定値を記載しています。同文書は helper 側 MMQ の丸めにより出力が default と bit-identical ではないため opt-in と説明しています。記載の性能値はその測定条件に限られ、他の構成で同じ改善が出るとはコードから確認できません。ソースの式も自動 share の説明と整合します。

## 根拠

- 値の読み取り、clamp、自動計算: `src/prefill/prefill.cpp:1532-1541`, `sycl/src/prefill/prefill.cpp:1519-1528`
- helper の初期化と適用条件: `src/prefill/prefill.cpp:1544-1581,1584-1646`, `sycl/src/prefill/prefill.cpp:1531-1595,1602-1687`
- 1 chunk への制限、share の実際の割り当て、観測ログ: `src/prefill/prefill.cpp:2083-2088,2313-2380,4183-4189`; SYCL `sycl/src/prefill/prefill.cpp:2149-2154,2463-2466,2519-2560`
- multi-GPU server からの helper 設定: `src/program/generate.cpp:7375-7386`, `sycl/src/program/generate.cpp:6948-6959`
- 説明と測定条件: `docs/MULTI_GPU.md:85-98`
