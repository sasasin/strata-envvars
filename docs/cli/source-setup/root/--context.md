# `--context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などから起動） |
| オプション | `--context` |
| 別名 | なし |
| 値 | 整数。parser に範囲指定はない。省略時はモデル経路ごとの対話選択または既定値を使う |

## 役割

モデルが一度に扱うコンテキスト長（token 数）を指定し、セットアップが生成する起動設定の `--max-context` に反映します。値が大きいほどコンテキスト用メモリが増えるため、通常のモデル経路では GPU / RAM の見積もり・警告、KV cache の設定、長文脈向け RoPE 設定にも影響します。`setup.py` の parser 定義は `type=int` のみで、`choices` や最小値・最大値を指定していません（`setup.py:8420-8435`）。

## 使い方

```sh
./setup.sh --setup --context 32768
```

Windows では `START-HERE.bat --setup --context 32768` のように指定できます。これらの wrapper は引数を `setup.py` に渡します（`setup.sh:6-12, 76`、`START-HERE.bat:8-10, 44-54`）。

## 値と既定値

- 整数以外は `argparse` の型変換で拒否され、通常の usage とエラーで終了します。parser は `--context` の既定値を `None` とし、数値範囲は検証しません（`setup.py:8425-8435`）。
- 通常の Qwen / Swift 経路では、未指定時に `CONTEXTS`（8192、32768、65536、131072、204800、262144、393216、524288）から選択します。`--yes` を使う場合は推奨値が選択されます（`setup.py:566`、`setup.py:9050-9069`）。
- 0 は複数の経路で `a.context or ...` または `if a.context` と扱われるため、明示値ではなく未指定時の選択・既定値に置き換わります（`setup.py:7581-7591, 9055-9069`、`setup.py:7980`、`setup.py:8275`）。負数を含む範囲外整数を共通 parser が拒否する処理は確認できません。負数を各エンジンがどう扱うかはこの調査では確認していません。

## 実行時の動作

### 通常の Qwen / Swift 経路

真値の明示値は対話選択を省略して採用されます。RAM 見積もり上の推奨を超える場合も値は変更せず、コンテキストが 131072 を超えて見積もり RAM に届かないと警告します（`setup.py:9050-9077`）。値は起動設定の `--max-context` に渡されます（`setup.py:9418-9425`）。

この経路では、訓練済み長の 262144 を超える場合、`--rope-scaling` も指定されていない対話実行では拡張方式を質問します。`--yes` では質問を出さず `resolve_rope` が `yarn` を選び、factor を最終コンテキスト / 262144（最低 1）から導出します。明示 `--rope-scaling none` は 262144 超で拒否され、`fail()` 経由でエラーになります。明示的な `--rope-scale` は指定値として保持されます（`setup.py:7286-7310, 9078-9096`）。

Unsloth の一部モデルを約 8 GB のカードで起動する際、見積もりが VRAM 不足なら setup はより小さいコンテキスト等の代替案を探します。ただし `--context` を明示すると `ctx_fixed=True` となり、その自動調整でコンテキストを変更しません（`setup.py:9540-9573`、調整順の説明は `setup.py:6993-7007`）。

### 別エンジン経路

- Qwen3.6 の own-path 経路では明示値を使い、未指定ならカードに応じて選びます。262144 超も警告して保持しますが、この経路には RoPE scaling がないと記されています（`setup.py:7580-7595`）。
- DeepSeek-V4.1-Flash は未指定時 8192 を使います。65536 超は未検証の警告を出して保持し、最終的に `--max-context` として起動設定へ渡します（`setup.py:734`、`setup.py:7980`、`setup.py:8026-8027`、`setup.py:8120-8129`）。
- macOS では `setup.py` が `metal/setup_mac.py` に引数を委譲します。同ファイルも `--context` を整数で受理し、未指定または 0 なら RAM に応じた推奨値を使い、測定済み上限を超えた値は知らせたうえで保持します（`setup.py:7314-7318`、`metal/setup_mac.py:327-356, 409-414`）。
- Intel Arc の SYCL 経路は `sycl/setup_intel.py` に委譲されます。明示 `--context` は VRAM fit 調整で固定値として扱われ、自動縮小の対象から外れます（`setup.py:7321-7338`、`sycl/setup_intel.py:317-329, 403-406`）。

## 適用条件と副作用

`--context` はセットアップ時のモデル選択・設定に使われる値です。既存モデルの通常起動は `--context` 単独をセットアップ条件として扱わず、既存 config を起動します。既存 config の設定変更には `--setup` などのセットアップ経路を使ってください（`setup.py:8617-8629, 8677-8692`）。`--update` と `--rollback-engine` はセットアップ処理より先に別処理へ分岐します（`setup.py:8614-8619`）。

セットアップ経路ではモデルの起動設定と `run-<model>.bat` / `.sh` に反映されます（通常経路の `--max-context` 組み立てと script 作成: `setup.py:9418-9425, 9730`）。大きな値はメモリ不足や未検証の長文脈動作につながり得ますが、通常経路では見積もりを超えても値を保持し、警告します（`setup.py:9070-9077`）。

## 出力とエラー

- 整数として解釈できない値は `argparse` が拒否します（`setup.py:8428, 8553`）。
- 262144 超の通常経路で `--rope-scaling none` を組み合わせると `resolve_rope` が `ValueError` を返し、setup は `fail(str(e))` を呼びます（`setup.py:7305-7310, 9088-9091`）。
- メモリ見積もりを超える値や、別経路で測定範囲を超える値は警告・案内を出して保持する経路があります（`setup.py:9070-9077`、`setup.py:7592-7595`、`setup.py:8026-8027`、`metal/setup_mac.py:411-414`）。

## 根拠

- `setup.py:8420-8435` — root parser の `--context` 宣言（整数、範囲制約なし）。
- `setup.py:566, 9050-9096` — 通常経路の候補値、既定選択、見積もり警告、RoPE 相互作用。
- `setup.py:9418-9425, 9540-9573, 9730` — engine 引数への反映、小容量カード時の調整、起動 script 作成。
- `setup.py:7580-7595, 7980, 8026-8027, 8120-8129` — Qwen3.6 / DeepSeek の各経路。
- `setup.py:7314-7338`、`metal/setup_mac.py:327-356, 409-414`、`sycl/setup_intel.py:317-329, 403-406` — platform / backend への委譲と各経路での扱い。
- `setup.py:8614-8629, 8677-8692` — update / rollback / 既存モデル起動時の適用条件。
- `setup.sh:6-12, 76`、`START-HERE.bat:8-10, 44-54` — wrapper が `setup.py` へ引数を渡すこと。

調査範囲は指定 commit の checkout に含まれるソースです。同 revision の既存 CLI help や Release artifact は実行・照合していません。負数など範囲外整数を下流 engine がどう扱うかも、この文書では断定していません。
