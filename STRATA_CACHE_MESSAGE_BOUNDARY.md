# `STRATA_CACHE_MESSAGE_BOUNDARY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の会話 prompt cache に、直近のユーザー入力より前にあるメッセージ境界の checkpoint を追加します。長い会話で最後の短いメッセージだけが変わった場合、通常の定期 checkpoint より先の状態から prompt を読み直せるようにするための opt-in です。

この変数は cache の再利用判定そのものを変えません。Strata は選んだ位置まで prompt を処理し、通常の会話 checkpoint と同じ状態 snapshot を保存します。次の request でも既存の token/image prefix 検査が再利用可否を決めます。

## 値と判定

CUDA と SYCL の server 実装は、どちらも `std::atoi(e) != 0` で判定します。文字列全体の比較ではなく、先頭の整数として変換できた値が 0 かどうかを見ます。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字、`true`、`abc`、`0`、`0suffix` | OFF（`atoi` の結果が 0） |
| `1`、`-1`、`2`、`1suffix`、` 1` | ON（`atoi` の結果が非 0） |

したがって、値が文字列 `1` と完全一致する必要はありません。符号と先頭空白を含む整数の後ろに文字があっても、整数部分が非 0 なら ON です。値を一度読むと関数ローカルの `static const bool` に保存されます。最初の該当 request で初期化され、その後プロセス内で環境変数を書き換えても再評価されません。

根拠: `src/program/generate.cpp:11003-11006`, `sycl/src/program/generate.cpp:10292-10295`。

## 有効になる条件

変数が ON でも、次の条件を満たすときだけ境界候補を作ります。

- server request の checkpoint が有効（request の `ckpt` が 0 でない）。`ckpt=0` では `turn_at` が `-1` にされ、この候補は作られません。
- `--prompt-cache` が正の値。既定値は 6、`--prompt-cache 0` なら無効です。
- layer split ではない（実装上の `multi_gpu` が false）。helper-expert GPU の利用だけでこの条件が false になるわけではありません。
- `--turn-token` が有効で、prompt 内に現在の turn boundary と、その直前にある別の turn token が見つかる。
- 直前の turn boundary の token index が 8,192 以上で、現在の boundary から 1,024 token 以内にある。

最後の二つの数値は `message_checkpoint_boundary()` の既定引数です。関数は現在の `turn_at` から後ろ向きに検索し、最初に見つかった前の turn token を候補にします。その token が `resume` より後でなければならず、prefix が 8,192 token 未満、または tail が 1,024 token を超える場合は候補を返しません。現在の turn token が無効、範囲外、または prompt 内の token と一致しない場合も候補はありません。

`--tail-role-token` によって最後の短い reasoning-effort turn を checkpoint から除外する設定では、`turn_at` がその直前の boundary に調整されます。`--turn-token` は既定で `248045`、`--tail-role-token` は既定で無効です。

根拠: `include/strata/program/message_boundary.hpp:9-17`, `src/program/generate.cpp:635-642,10977-11009`, `sycl/src/program/generate.cpp:10265-10298`。

## 実行時の詳細

有効な候補 index は prompt 読み込みの `cuts` に追加されます。Strata はそこまでの token を通常の prompt read path で処理し、境界に着いたら `checkpoint_at()` を呼び、会話状態の snapshot を `checks` に保存します。同じ長さの checkpoint が既にあれば新しい snapshot は作らず、その既存 checkpoint の使用 stamp を更新します。message-boundary 位置が turn/root/pin の位置と異なる場合は tail checkpoint として扱われ、checkpoint 数が `--prompt-cache` の上限を超えたとき、最新の checkpoint を除く tail checkpoint が通常 checkpoint より先に eviction 対象になります。

この追加位置は既存の prompt read を分割する場合があります。そのため checkpoint の保存・分割コストが生じ、短い prompt では余分な処理になる可能性があります。trace が有効な場合、保存時に stderr へ `strata serve: message boundary checkpoint: %lld tokens, %lld tail` を出します。trace が無効なら、この候補が採用されたことを示す専用ログはありません。

根拠: `src/program/generate.cpp:8026-8090,11033-11090`, `sycl/src/program/generate.cpp:10297-10300,10343-10350`, `include/strata/program/conv_cache.hpp:43-55`。

## 文書との照合

`docs/MESSAGE_BOUNDARY_CACHE.md:13-19` も既定 OFF、prompt cache が必要、8,192 token 以上の prefix、1,024 token 以下の tail、layer-split 除外を説明しており、現行コードと一致します。同文書の性能表は境界方式と chunk size を同時に変えた過去の比較であり、この環境変数単独の効果を測った値ではありません。そのため本調査では性能向上率をこの変数の効果として記載しません。

## 根拠

- 読み取りと有効条件: `src/program/generate.cpp:11003-11009`, `sycl/src/program/generate.cpp:10292-10298`
- 境界選択の条件: `include/strata/program/message_boundary.hpp:9-17`
- request の turn boundary と prompt cache 設定: `src/program/generate.cpp:615,635-642,10977-11009`
- checkpoint の作成と cache 上限: `src/program/generate.cpp:8026-8090,11033-11090`
- tail checkpoint の eviction 規則: `include/strata/program/conv_cache.hpp:43-55`
- 機能説明と測定値の制約: `docs/MESSAGE_BOUNDARY_CACHE.md:13-19,30-50`
