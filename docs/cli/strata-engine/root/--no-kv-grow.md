# `--no-kv-grow`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。実行は `strata generate`） |
| オプション | `--no-kv-grow` |
| 別名 | なし |
| 値 | なし（フラグ） |

## 役割

K/V cache を要求の到達セル数に応じて拡張する elastic K/V 機能を、CLI から無効にするフラグです。parser は `Options::kv_grow` を `false` にします。初期値も `false` なので、環境変数による上書きがなければ省略時も無効です（`src/program/generate.cpp:488,2482-2483`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-kv-grow
```

`--no-kv-grow` 自体に値は付けません。`--tokens` はこの例で必要な入力を示しています。

## 値と既定値

- parser は値を読み取らず、出現時に `o.kv_grow = false` とします。数値・真偽値の validation はありません（`src/program/generate.cpp:2482-2483`）。
- `--kv-grow` と併用した場合、引数列を順に処理して同じ boolean を設定するため、後に現れた方が parser 上の値になります（同:2482-2483）。
- ただし、非空の `STRATA_KV_GROW` が設定されていると環境変数が CLI の設定より優先します。値の先頭文字が `0` なら無効、それ以外なら有効です。したがって `STRATA_KV_GROW=1` や `STRATA_KV_GROW=false` は `--no-kv-grow` より優先して有効化し、`STRATA_KV_GROW=0` は無効化します。空文字または未設定なら CLI flag の値を使います（同:5199-5203）。

## 実行時の動作

エンジン起動時、elastic K/V を有効にする条件を判定し、`qsa_set_kv_elastic(on, ...)` と `ExpertCache::set_vmm(on)` に結果を渡します。`--no-kv-grow` により要求値が無効なら、elastic K/V 用 VMM pool と ExpertCache の連携を有効にしません（`src/program/generate.cpp:5196-5213`、`src/core/layer.cpp:680-684,813-835`）。

無効時は K/V を要求に応じて拡張する elastic 経路に入りません。elastic pool は `g_kv_elastic && p.mode == 0` のときだけ作られ、それ以外では通常の K/V allocation 経路に進みます（`src/core/layer.cpp:813-835`）。`--kv-resident` が 0（既定）の通常配置では、help は `--max-context` 全体を起動時に確保すると説明しています（`src/program/generate.cpp:833-839`）。`--kv-resident` を正数にした streaming 配置は別経路であり、elastic K/V の有効条件から除外されます（同:5202-5207）。

CLI で無効を指定しても `STRATA_KV_GROW` が非空なら、その環境変数の判定結果が使われます。また環境変数で有効を要求していても、以下の条件を満たさない場合は機能が無効になります（`src/program/generate.cpp:5202-5210`）。

- GPU が1台である。
- `--kv-resident` が 0 以下で、K/V streaming を使わない。
- `--expert-profile` が指定され、resident CPU expert mode ではない。
- expert cache が無効値 `0` ではなく、remote expert cache を使わない。
- VMM が利用可能である。
- `--batch` が 0、`--vram-elastic` が未指定、`--peer-device` が未指定である。

さらに実際の拡張管理は、VMM cache range、device residency table、host residency、source profile があり、cache slot 数が floor より大きい場合に開始されます（`src/program/generate.cpp:7869-7883`）。無効時にはこの管理経路の grow/trim が行われません。

## 適用条件と副作用

このフラグ自体に OS や backend 固有の validation はありません。VMM 機能が無効、または上記の構成条件を満たさない場合、elastic K/V は有効になりません。要求が有効だったのに条件を満たせなかった場合は stderr に `--kv-grow is off (...)` の警告を出します。要求自体が無効なら、この警告は出しません（`src/program/generate.cpp:5202-5210`）。

`--kv-resident` が 0 の通常配置で elastic K/V を無効にすると、K/V は `--max-context` 全体を起動時に保持します。elastic 時に K/V が利用要求に応じて占有する VRAM を増やす動作はなくなります。`--kv-resident` による streaming 配置ではこの起動時全量 VRAM allocation の説明は当てはまりません。一方、起動時 allocation が失敗すると、session state allocation または session initialization のエラーを stderr に出して終了コード 1 で終了します（`src/program/generate.cpp:5215-5221`）。

## 出力とエラー

- `--no-kv-grow` の値に関する専用エラー経路はありません。
- オプション名自体が parser に認識されなければ、`unknown argument: ...` を stderr に出し、usage を表示して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。
- elastic K/V が要求されたが適用条件を満たさない場合の警告は、上記のとおり stderr に出ます。`--no-kv-grow` を単独で使う場合は要求値が無効なので、この警告条件には該当しません（同:5208-5210）。
- 通常 K/V の起動時確保が失敗したときは `session state allocation failed` または `session_init failed` を stderr に出し、終了コード 1 になります（同:5215-5221）。

## help と索引の差異

この revision の `strata generate --help` usage には `--kv-grow` と既定動作の説明がありますが、`--no-kv-grow` は掲載されていません（`src/program/generate.cpp:836-839`）。一方、parser には `--no-kv-grow` が実装されています（同:2482-2483）。索引では `strata-engine` の `strata`（エンジン引数）スコープに本書へのリンクがあり、指定された `strata-engine/root` の配置と一致します（`docs/cli/README.md:1128-1134,1231`）。索引は変更していません。

## 根拠

- parser と option 初期値: `src/program/generate.cpp:488,2482-2483`
- 組み込み help の掲載内容: `src/program/generate.cpp:836-839`
- 環境変数優先順位、適用条件、警告: `src/program/generate.cpp:5196-5213`
- 起動時 allocation error: `src/program/generate.cpp:5215-5221`
- elastic K/V pool の条件と初期 allocation: `src/core/layer.cpp:680-684,813-835`
- elastic K/V の grow 管理開始条件: `src/program/generate.cpp:7869-7883`
- unknown argument の失敗経路: `src/program/generate.cpp:2787-2792`
- 利用者向け説明（ソース parser との照合用）: `docs/DETAILS.md:366-372`
