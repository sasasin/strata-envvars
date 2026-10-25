# `STRATA_SPLIT_OWN_PLACE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。作業ツリーは `main`、HEAD と `origin/main` は一致し、調査時に未コミット変更はありませんでした。外部ライブラリの環境変数は対象外です。

## 役割

`STRATA_SPLIT_OWN` の自動判定によって layer split の各 GPU が独自の prompt buffer を持つ場合に、`--layer-split auto` の配置探索でその buffer 用 VRAM を予約量として差し引くかを切り替えます。値が `reserve` なら探索時にも予約を差し引き、未設定または別の値なら探索は予約なしで配置を選びます。探索後の各 GPU の expert cache の容量決定では、独自 buffer 分の予約はどちらの設定でも差し引かれます。

したがって、この変数は独自 buffer を有効にする設定ではなく、独自 buffer が選ばれた場合の自動分割位置に影響する調整用設定です。独自 buffer を使うかどうかは `STRATA_SPLIT_OWN` が決めます。

## 値と判定

`std::getenv()` で値を読み、文字列全体を `"reserve"` と比較します。数値変換や前後空白の除去、大文字小文字変換はありません。

| 値 | `place_with_reserve` | `split_own_auto=true` のときの探索時の扱い |
|---|---:|---|
| 未設定 | false | 独自 prompt buffer の予約を探索容量から差し引かない |
| 空文字 | false | 同上 |
| `reserve` | true | `split_pf_mib` を予約量に含める |
| `RESERVE`、`1`、`true`、` reserve` など | false | 同上 |

値は関数内の `static const bool` として初回到達時に評価・保存されます。プロセス実行中に環境を変更しても、その後の呼び出しで再評価されません。

根拠: `src/program/generate.cpp:3797-3800`、SYCL 実装 `sycl/src/program/generate.cpp:3546-3549`。

## 有効になる条件

この値が配置に影響するには、次の条件が必要です。

- 複数 GPU の layer split である。
- `--layer-split auto` が使われている。
- `STRATA_SPLIT_OWN` により独自 prompt buffer が自動選択され、内部フラグ `split_own_auto` が true になっている。

`split_own_auto` は、`--no-prefill-borrow` が指定されておらず、`--split-skip-if-fits` も指定されていない状態で、`STRATA_SPLIT_OWN` が `0` で始まらない値に設定されている場合にだけ検討されます。値が `auto` なら全 split GPU の VRAM 容量を調べ、prompt buffer の推定量が各 GPU の総 VRAM の 12% 以下の場合に独自 buffer を選びます。`1` で始まる値なら明示的に選びます。`STRATA_SPLIT_OWN` の未設定または先頭文字 `0` はこの選択を行いません。独自 buffer が選ばれない場合、`STRATA_SPLIT_OWN_PLACE` の値に関係なく探索時に差し引く `split_pf_mib` は配置に影響しません。

また、`--layer-split` に明示的な境界を渡した場合は配置探索をしないため、この変数の探索時効果はありません。`--split-skip-if-fits` によって単一 GPU 実行へ戻る場合も `split_own_auto` は立ちません。

根拠: `src/program/generate.cpp:2407-2408,2449-2485,3814-3815`。独自 buffer と `STRATA_SPLIT_OWN` の利用者向け説明は `docs/MULTI_GPU.md:76-83` にあります。

## 実行時の詳細

独自 prompt buffer の予約量 `split_pf_mib` は、`--prefill` の chunk が正の場合、`160 + (chunk * 680) / 1024 + split_ring_mib` MiB です。独自 buffer が有効な split で chunk が 1024 以上なら、96 個の expert blob 用 split ring のサイズも加算されます。chunk が 1024 未満、または split でない場合、ring 加算は 0 です。`--prefill` が自動の場合の chunk は、独自 buffer 判定時には 2048 として見積もられます。根拠: `src/program/generate.cpp:2458-2460,3731-3741`。

`stage_room()` は探索中 (`search=true`) かつ `split_own_auto=true` で、さらに `STRATA_SPLIT_OWN_PLACE` が `reserve` でない場合、探索用容量から差し引く prompt buffer 予約 `pf` を 0 にします。`reserve` の場合は `split_pf_mib` を含めて各 stage の使用可能 VRAM を見積もります。`split_own_auto=false` の場合はこの環境変数による切り替えはなく、通常どおり `split_pf_mib` を使います。いずれも `--vram-reserve-mib`（後続 GPU 用の指定があれば `--vram-reserve-later-mib`）、verify window、pipeline window、drafter/head の予約は別途差し引かれます。

探索が終わって cache を実際に確保する際は `search=false` で `stage_room()` が呼ばれるため、`STRATA_SPLIT_OWN_PLACE` の値にかかわらず `split_pf_mib` が差し引かれます。このため、既定の探索は独自 buffer の予約を無視して境界を選び、その後の cache が小さくなる場合があります。`reserve` は探索モデルにも実際の予算を反映させ、選ばれる layer 境界や予測値を変えることがあります。どの境界が選ばれるかは GPU の空き VRAM、各 stage の session サイズ、profile、リンク速度などにも依存します。

CUDA と SYCL の `generate.cpp` に同じ値比較と `stage_room()` の予約条件があります。実装上、環境変数専用のログはありません。`--layer-split auto` の通常の起動ログには、選ばれた `K`、予測 decode window 時間、profile 上の cache 保持量が出ます。

根拠: `src/program/generate.cpp:3797-3812,3814-3826,4287-4292,5552-5563`、`sycl/src/program/generate.cpp:3546-3567`。

## 文書・測定との照合

`docs/MULTI_GPU.md:76-83` は `STRATA_SPLIT_OWN=1` と `auto` の独自 prompt buffer 選択条件を説明していますが、`STRATA_SPLIT_OWN_PLACE` の説明はありません。ソースコメント (`src/program/generate.cpp:3761-3765`) には、予約込みの探索で境界が `K=28` から `K=32` に変わり、decode が 54.8 tok/s になった比較として、R9700 + RX 9070 XT の測定値が記録されています。ただし、これはソースコメントの記録であり、モデルや測定条件の詳細が揃っていないため、この文書では一般的な性能効果として扱いません。
