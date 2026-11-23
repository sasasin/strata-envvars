# `STRATA_EXPERT_NIBBLE_RECHECK`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

4-bit expert slot をロード時に記録した hash と、各リクエスト後に計算した hash とで比較する診断用スイッチです。値を `1` にしても 4-bit slot 化自体は有効にならず、`STRATA_EXPERT_NIBBLE` によって実際に slot が変換されている場合だけ再検査します。対象は Strata の generate/serve 処理が持つ primary cache と layer-split 各 stage の変換済み slot です（`engine/include/strata/core/expert_nibble.hpp:213-219,238-248`、`engine/src/program/generate.cpp:23305-23315`）。

## 値と判定

`std::getenv` の戻り値を文字列全体で `"1"` と `strcmp` します。数値変換や真偽値文字列の解釈はありません。未設定と空文字は無効で、`1` だけが有効です。`0`、`01`、`1 `、`true`、`True`、空白だけの値などはすべて無効になり、無効値自体への警告やエラーはありません（`engine/include/strata/core/expert_nibble.hpp:247-248`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| すべての build での値判定 | `recheck=false` | 文字列全体が `1` | 空文字、`0`、`01`、`1 `、`true` など |
| 変換済み slot の再検査 | 再検査しない | 上記 `1` かつ `nib::any_on()` | 上記以外、または変換済み slot がない |

## 有効になる条件

- `STRATA_EXPERT_NIBBLE=1` が別途必要です。この変数だけでは slot を変換しません。形式選択の `STRATA_EXPERT_NIBBLE_FMTS` と除外層の `STRATA_EXPERT_NIBBLE_SKIP` によって変換対象がなくなった場合も、`nib::any_on()` が false となり再検査しません（`engine/include/strata/core/expert_nibble.hpp:213-219,247-267`、`engine/src/program/generate.cpp:5446-5456,23305`）。
- 有効化には compute capability 6.0 の全 CUDA device、4-bit slot と互換性のある環境設定・CLI、全 expert の profile 常駐も必要です。競合設定やオプション等により Nibble が無効になる場合、起動時に警告を出して通常の GGUF slot で続行します。全 expert が各 layer の実行 device の cache に常駐していなければ起動を拒否し、条件を満たすと cache を seal して以降 slot への書き込みを止めます。prompt MMQ の経路も変換 slot ごとに互換性を確認します。これらは本変数が条件を変えるものではありません（`engine/src/program/generate.cpp:3403-3435,5446-5461,9957-9989`、`engine/src/prefill/prefill.cpp:3915-3937`）。
- CLI 引数による本変数の上書きはありません。`STRATA_EXPERT_NIBBLE_RECHECK` は独立して読み取られ、他の値に fallback しません（`engine/include/strata/core/expert_nibble.hpp:238-248`）。

## 実行時の詳細

設定は `nib::config()` 内の関数 static `Config` として初回アクセス時に一度だけ読み取られます。generate.cpp では Nibble の起動判定時にアクセスし、その後はキャッシュ済みの `recheck` 値を参照します。プロセス起動後の環境変更は反映されません（`engine/include/strata/core/expert_nibble.hpp:238-269`、`engine/src/program/generate.cpp:5446,5480,23305`）。

Nibble の slot 変換時、各 slot の hash は `d_ref` に記録されます（`engine/src/program/generate.cpp:3241-3279`）。各リクエストの処理後、キャンセルされておらず、かつ変換済み slot がある場合に、primary cache と各 stage の slot をそれぞれの device 上で再 hash し、ロード時の値と比較します。対象は slot の先頭から `hashed` bytes、すなわち 4-bit gate/up 部分と down rows で、未書き込みの alignment tail は含みません（`engine/include/strata/core/expert_nibble.hpp:190-207,303-310`）。キャンセルされたリクエストではこの検査を飛ばします（`engine/src/program/generate.cpp:3350-3382,23305-23315`）。

## ログと測定値

検査が成功すると、リクエストごとに stderr へ次の形式で件数と所要時間を出します（実際の数値は実行時に決まります）。

```text
strata serve: STRATA_EXPERT_NIBBLE_RECHECK: <件数> 4-bit slots hash as at load (<ミリ秒> ms)
```

ハッシュ不一致時は、まず `strata serve: STRATA_EXPERT_NIBBLE_RECHECK: CUDA<device>: layer <layer> expert <expert> (slot <slot>) hashes <現在値>, <ロード時値> at load` を stderr に出し、続けて `strata: STRATA_EXPERT_NIBBLE: layer <layer> (<format>, 4-bit slots) reached STRATA_EXPERT_NIBBLE: a slot changed after the load - stopping` を出して `abort` します。hash kernel の起動・同期・読み戻しで CUDA error が起きた場合も `strata serve: STRATA_EXPERT_NIBBLE_RECHECK: <エラー>` を出し、stderr を flush して `abort` します（`engine/src/program/generate.cpp:3352-3380,23317-23324`、`engine/include/strata/core/expert_nibble.hpp:396-400`）。

Strata の資料にはこの再検査の性能測定値はありません。`docs/OLDER_GPUS.md:230-231` の説明は「各リクエスト後に全 4-bit slot を hash する」という動作で、実装と一致します。

## 根拠

- `engine/include/strata/core/expert_nibble.hpp:33-38` — 4-bit kernel を含む build macro 条件。
- `engine/include/strata/core/expert_nibble.hpp:213-269` — 設定構造体、値の厳密比較、static cache。
- `engine/src/program/generate.cpp:3241-3279` — 変換時の初回 hash 記録。
- `engine/src/program/generate.cpp:3350-3382` — 再 hash、比較、エラー詳細。
- `engine/src/program/generate.cpp:3384-3435,5446-5461,9957-9989` — build / device / option / residency 条件と Nibble の有効化・無効化。
- `engine/src/prefill/prefill.cpp:3915-3937` — prompt MMQ が変換 slot を扱えるかの条件。
- `engine/src/program/generate.cpp:23305-23324` — リクエスト後の実行条件、ログ、失敗時の停止。
- `engine/include/strata/core/expert_nibble.hpp:396-400` — fatal ログと abort。
