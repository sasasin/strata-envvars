# `STRATA_PREFILL_HELP_FRAC`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_PREFILL_HELP=1` で有効にする layer split の prompt help で、各 stage がストリームする expert のうち、次 stage の idle GPU に計算を任せる割合を固定します。割合は prompt chunk の token 数 `T` ごとに再計算されますが、この環境変数が指定されている場合は全 `T` で同じ値を使います。CUDA と SYCL の実装に同じ判定があります。

## 値と判定

この変数は `std::atof` で読み、結果を `[0.0, 1.0]` に `std::clamp` します。文字列全体の妥当性検査はありません。未設定なら固定値の印として `-1.0` を返し、token 数に応じた既定式へ進みます。設定済みなら空文字や数値に変換できない文字列も `atof` により `0.0` となり、help の割合を 0 にします。

| 値の例 | 固定割合の扱い |
|---|---|
| unset | 自動割合を使う |
| `0.25`, `1`, `2` | それぞれ `0.25`, `1.0`, `1.0`（上限で clamp） |
| `-0.2`, `0`, 空文字、`abc` | `0.0`（下限で clamp、または `atof` の変換結果） |
| `0.2tail` | `atof` が先頭の数値部分を変換し `0.2` とする |

`nan` など `atof` が NaN を返す文字列では、比較による clamp を通過して NaN が残ります。`fixed >= 0.0` が成立しないため、その呼び出しでは自動割合の式が使われます。変数の値は `split_help_frac()` 内の `static const double` に初回呼び出し時に保存され、プロセス実行中に環境を書き換えても再読込されません。

未設定時の自動割合は `f = min(0.45, 0.5 - T / 16384.0)`。`f >= 0.3` のとき `f`、それ未満なら `0.0` です。したがって正の整数 `T` では `T <= 3276` で割合が正、`T >= 3277` で 0 になり、`T <= 819` では上限 0.45 になります。

## 有効になる条件

この割合だけでは help を有効にしません。`STRATA_PREFILL_HELP` が `std::atoi(value) != 0` で有効になっており、layer split で helper GPU が設定されている必要があります。さらに prompt が単一 chunk で、`T >= stream_all_min()`, expert source があり、ring が `STAGE` より大きく、fused ring が使われず、各 layer が MMQ plan に含まれ、対応する native fused expert format がない等の条件を満たす場合にだけ `bind_stage_helper()` が成功します。割合が 0 以下ならここで help は無効になります。

この helper 経路は CUDA / SYCL の Strata prefill 実装です。設計資料は `--peer-device` と `STRATA_PF_FUSED=1` では使えないこと、native pack の MMQ prompt path が対象であることを説明しています。別途、CUDA と SYCL それぞれで ring、source、MMQ layer、native fused support の条件を検査します。

## 実行時の詳細

serve の multi-GPU layer split 初期化時に各 prefill stage が次の stage を `set_stage_helper()` に渡します。`STRATA_PREFILL_HELP` が有効なときに helper 用の stream/event 等を準備し、chunk 処理中は `single_chunk && bind_stage_helper(n)` の場合だけ helper ring に切り替えます。`bind_stage_helper()` がこの環境変数から得た割合を `PeerPrefill::ps_frac` に設定します。

stream-all の expert 計画では、stable かつ pinned な expert blob ごとに累積値へ `ps_frac` を加算し、累積値が 1 以上になった expert を helper GPU の peer ring に割り当てます。選ばれた expert は通常 stage 側の列から除かれ、helper GPU が MMQ でその行を計算して返します。よって値は割合に近い選別を行い、対象となるのは pinned expert であり、割合そのものを GPU 使用率や全 expert 数に対する厳密な比率として保証するコードではありません。

CUDA 側は prefill timing が有効な経路で peer-streamed expert 数を stderr に記録します。変数自体について専用のログ文言はありません。処理の詳細・測定値は `docs/MULTI_GPU.md` の説明にあり、コードコメントの測定例は 2x RTX 3090、UD-Q4_K_XL、PCIe 4.0 x16、P2P なしの条件です。これらは当該資料・コメントに記載された測定値で、他環境の性能を示すものではありません。

## 根拠

- `src/prefill/prefill.cpp:1570-1579`, `sycl/src/prefill/prefill.cpp:1521-1530`: 環境変数の読み取り、変換、clamp、自動割合。
- `src/prefill/prefill.cpp:1582-1619`, `sycl/src/prefill/prefill.cpp:1533-1597`: layer split helper の初期化と環境変数 `STRATA_PREFILL_HELP` による有効化。
- `src/prefill/prefill.cpp:1624-1663`, `sycl/src/prefill/prefill.cpp:1606-1645`: token 数・実行条件の検査と `ps_frac` の設定。
- `src/program/generate.cpp:7700-7710`: serve 初期化時に stage ごとの helper を設定。
- `src/prefill/prefill.cpp:2122-2138`, `2341-2353`, `2390-2419`: 単一 chunk での helper 利用、stream-all 条件、割合による pinned expert の peer ring 選択。
- `docs/MULTI_GPU.md:85-98`: 公開資料の機能条件、動作説明、測定条件と測定値。
