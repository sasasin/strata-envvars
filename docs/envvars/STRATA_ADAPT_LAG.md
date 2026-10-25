# `STRATA_ADAPT_LAG`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

適応層（adaptive tier）が選んだ expert の入れ替えについて、次の decode window がその入れ替えを適用する前に何 window 待つかを指定します。既定値 `1` は次の window でコピー完了を待ってから適用します。`2` なら pending の入れ替えをもう 1 window 保留し、2 window 目にコピーを待って適用します。値を大きくすると、その間は従来の residency table に基づいて window を実行します。

環境変数は `adapt_lag()` の `static const int` に一度だけ読み込まれます。値を初めて評価した後、プロセス実行中に環境を変更しても反映されません。読み取り関数は CUDA 系と SYCL 系の `generate.cpp` にそれぞれあります。

## 値と判定

| 環境変数の状態・値 | 判定結果 |
|---|---|
| 未設定 | `1` |
| 空文字 | `atoi("")` が `0` となり、下限 clamp により `1` |
| 数値文字列 | `atoi` で整数変換し、`1` 未満なら `1` |
| 数字で始まらない文字列 | `atoi` が `0` を返すため `1` |
| 先頭に空白・符号がある文字列 | `atoi` の規則で先頭の空白と符号を読み、その後の数字列を変換。数字列の後ろの文字は無視される |
| `0`、負数 | `1` |
| `2` 以上 | 変換された整数値 |

コードは `std::max(1, std::atoi(e))` を使い、文字列全体の妥当性確認はしません。たとえば `2junk` は `2`、`+3` は `3`、`-2` は `1` と判定されます。数値変換可能範囲を超える文字列の結果は文書化しません。

## 有効になる条件

- 適応層が有効で、pending の expert 入れ替えがある decode 経路で使われます。適応層が無効なら待つ入れ替えがないため、この値による動作差はありません。
- 通常の逐次 decode 経路で window ごとに pending age を進め、値に達したときコピー完了を待って入れ替えを反映します。pending が空ならその window で適用待ちを行いません。
- `STRATA_ADAPT_NOWAIT` が有効な経路は `apply_pending(false)` を呼び、lag の待機条件を通りません。
- `STRATA_ADAPT_OVERLAP` の有効化条件は `adapt_lag() == 1` です。値が `1` 以外の場合、overlap は無効になり、明示的に `STRATA_ADAPT_OVERLAP` を設定していると「not with STRATA_ADAPT_LAG / STRATA_ADAPT_NOWAIT」の理由が stderr に出ます。
- ソースコメントでは batch paths と `--pipeline-windows` は lag の対象外とされています。peer tier は独立の pending なら `pending.empty()` の分岐から毎 window 適用されます。一方 CUDA 系の共通 `apply_pending(wait)` は peer にも同じ `wait` を渡すため、通常の adaptive tier にも pending がある場合は peer 側の pending も同じ呼び出しまで待つことがあります。

## 実行時の詳細

CUDA 系および SYCL 系の逐次 decode loop は `pending_age` を `0` で初期化します。通常経路では window ごとに pending があれば `++pending_age >= adapt_lag()` を評価し、しきい値に達したとき `apply_pending(true)` を呼びます。CUDA 系では pending のコピー event を同期し、resident table を更新して pending を空にし、`pending_age` を `0` に戻します。したがって `N` はコピーを適用するまでの window 数であり、`N=1` が既定、`N=2` 以降は opt-in の遅延です。CUDA 系の `apply_pending` は最初に `peer.apply_pending(wait)` を呼ぶため、通常 tier と peer tier の両方に pending がある場合は peer の適用もこの待機回に揃います。通常 tier が空なら `pending.empty()` が true となり `apply_pending(true)` が呼ばれるので、peer 単独の pending は lag されません。

実装は CUDA と SYCL の両方にあり、それぞれ speculative decode と通常の generate 経路に読み取り関数と window 判定があります。GPU/backend ごとに値の parse 規則は異なりません。適用中のログや警告をこの変数自身が出す箇所は確認できません。

## 文書・測定値

`docs/DETAILS.md` も既定値 `1`（0.1.39 相当）と `STRATA_ADAPT_LAG=2` の opt-in を説明しています。同資料の測定では Tesla P100（PCIe 3.0 x16）で 6 組中 6 組が速く、RTX 5070 は +0.2%（4/6 組）、RTX 3060 は -1.3%（0/6 組）だったため既定 off ではなく値 `1` を維持したと記載されています。これらは資料に記載された条件の結果であり、他の機器やモデルでの性能を保証しません。別の `docs/MULTI_GPU.md` の表には、特定構成で `STRATA_ADAPT_LAG=2` の結果（decode 142.8 tok/s、prefill 1800 tok/s）が記載されていますが、同資料の表注記にある構成・測定回数の範囲に限られます。

## 根拠

- `src/program/generate.cpp:1320-1327`, `sycl/src/program/generate.cpp:1275-1279`: `atoi`、既定値、下限 clamp、static cache。
- `src/program/generate.cpp:8266-8269,8315-8336,11856-11876,13065-13069`, `sycl/src/program/generate.cpp:7761,7805,11148-11153,12115,12362-12367`, `src/core/peer_experts.cpp:321-330`: pending age の初期化・適用・リセット、decode loop の判定、peer pending の適用。
- `src/program/generate.cpp:8285-8286,8303-8304`: overlap が lag 値 `1` を要求する条件と、明示設定時の stderr 理由。
- `docs/DETAILS.md:268-269,1697-1698`: 既定値と測定値。
- `docs/MULTI_GPU.md:318-328`: 記載された multi-GPU 構成と `STRATA_ADAPT_LAG=2` の表値。
