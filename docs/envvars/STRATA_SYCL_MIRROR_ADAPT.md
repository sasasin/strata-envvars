# `STRATA_SYCL_MIRROR_ADAPT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の `--serve` 実行で、NoHost verifier が数えた expert routing の使用量を適応型 VRAM expert cache に渡し、VRAM cache 内の低使用 expert と、VRAM にない高使用 expert を pinned host mirror と交換する経路を選ぶ。変数が無効ならこの専用経路は使われず、通常の適応 tier が使われる（`sycl/src/program/generate.cpp:5363-5370,5373-5384,8426,8509-8565`）。

Verifier は各 window の routed expert ID を device 上で集計し、完了時に controller の usage vector へ加算する。交換時は cache slot と mirror address table を更新する。したがって変わるのは expert の配置と読み取り元であり、この変数自体は token の選択や sampling 設定を読まない（`sycl/src/core/verify.cpp:81-96,1531-1533,2663-2677`; `sycl/src/program/generate.cpp:8536-8565`）。

## 値と判定

両読み取り箇所とも `std::getenv` の結果が存在し、先頭文字が `'1'` の場合だけ有効。文字列全体の比較や数値変換はしない。未設定・空文字・先頭が `'1'` 以外なら無効であり、大文字小文字や後続文字は判定しない（`sycl/src/core/verify.cpp:73-79`; `sycl/src/program/generate.cpp:140-147`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL verifier / generate | 無効 | `1`, `10`, `1anything` | 空文字, `0`, `true`, `false`, `01`, ` 1` |

## 有効になる条件

- Strata の SYCL 実装経路であること。ここで確認した読み取り箇所は `sycl/src/` 以下にあり、この変数を CUDA/HIP 側で読む実装はない。
- generate 側の cache 初期化時に、`--serve`、`--stream-experts`、GGUF source、単一 GPU（stage split なし）、peer/remote cache なし、`--no-prefill-borrow`、VRAM elastic 無効、全ての VRAM 外 expert を mirror 済み、`--adapt-every > 0`、`1 <= --adapt-swaps <= 96`、`--expert-profile-save` 未指定であること。いずれかを満たさないと `stderr` に `SYCL mirror adaptive cache requires single-device complete stream mirror, no borrow/elastic/profile save` を出して `return 1` する（`sycl/src/program/generate.cpp:5373-5384`）。
- Verifier 初期化時に device planning が有効で、`STRATA_VERIFY_NO_HOST` が `env_on` 判定を通ること。`env_on` は unset、空文字、先頭が `'0'` の値を false、それ以外の非空文字列を true と判定する。不成立なら `mirror adaptive expert usage requires NoHost device planning` の `runtime_error`（`sycl/src/core/verify.cpp:149-152,899-906`）。
- route 使用量を accumulation するための `drive.d.usage` vector が割り当てられていること。generate は適応設定が有効かつ全 expert が VRAM resident ではない場合に割り当てる（`sycl/src/program/generate.cpp:8397-8403`）。
- `STRATA_SYCL_ADAPT_WINDOW_PRESENCE=1` の場合、対象 expert の window 内使用回数を生の回数でなく 0/1 にして controller vector に加算する。これも先頭文字が `'1'` かで判定される（`sycl/src/core/verify.cpp:2673-2677`）。

## 実行時の詳細

generate 側の設定チェックは stream cache と mirror の構築後に行われる。全ての VRAM 外 expert が mirror に揃っていない場合、先行する通常の NoHost miss check が `REFUSED` と理由・対処を `stderr` に出し、終了 code 2 で拒否する（`sycl/src/program/generate.cpp:5354-5361`）。

Verifier は `init()` で layer × expert サイズの host/device histogram をゼロ初期化する。各 layer の routing 後に window 内の route ID を数え、window 完了時に histogram を host にコピーする。合計が `(layer 範囲) × T × ss.k` と一致しなければ `mirror adaptive route histogram coverage mismatch`、usage vector が未 bind またはサイズ不一致なら `mirror adaptive expert usage is unbound` / `mirror adaptive expert usage shape mismatch` を例外にする。成功した NoHost window の使用量だけが controller に加算される（`sycl/src/core/verify.cpp:899-906,1531-1533,2338-2340,2663-2677,4480-4484`）。

generate は `drive.d.usage` を verifier に bind する。適応実行時、各 layer で VRAM 外 expert のうち使用量が 2.0 以上のものを候補にし、resident expert と比較する。候補使用量が resident 使用量を 1.5 超える場合に交換候補とする。この環境変数が有効な経路では、同数時の順序を layer/expert 順に安定化する。最大 `--adapt-swaps` 件を交換し、mirror table を再転送した後、usage を `--adapt-decay` 倍にする。実行時点は serving decode loop の適応周期による（`sycl/src/program/generate.cpp:8426,8509-8565,12401-12408`）。

SYCL mirror の交換は同期実行される。交換失敗、mirror complement の欠落、mirror/cache の重複があれば具体的な `stderr` メッセージを出し、adaptive exchange failure により generation は終了 code 1 で戻る（`sycl/src/program/generate.cpp:8536-8565,12402-12408`）。

両 `sycl_mirror_adapt()` はそれぞれの翻訳単位の関数内 `static` に最初の判定結果を保持する。したがって各関数の初回呼び出し後にプロセス環境が変わっても、その関数の判定には反映されない（`sycl/src/core/verify.cpp:73-79`; `sycl/src/program/generate.cpp:140-147`）。

## ログと測定値

条件を満たして機能が有効なら起動時に `SYCL mirror adaptive cache: sync exchange; %lld slots, %lld cache bytes, %llu mirror bytes` を `stderr` に出す。設定不一致、NoHost 条件不成立、histogram の不整合、交換失敗時のメッセージは上記の通り。対象変数による性能測定値は確認できない（`sycl/src/program/generate.cpp:5379-5383,8544-8558`; `sycl/src/core/verify.cpp:901,2664-2671`）。

## 根拠

- 環境変数の parse と cache: `sycl/src/core/verify.cpp:73-79`; `sycl/src/program/generate.cpp:140-147`
- 条件・初期化・起動ログ: `sycl/src/core/verify.cpp:899-906`; `sycl/src/program/generate.cpp:5354-5384`
- histogram 集計・usage 反映: `sycl/src/core/verify.cpp:81-96,1531-1533,2338-2340,2663-2677,4480-4484`
- cache 交換と decode loop: `sycl/src/program/generate.cpp:8426,8509-8565,12401-12408`
- 適応設定の既定値: `sycl/src/program/generate.cpp:681-710`
