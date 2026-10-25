# `strata launch --kv`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--kv FORMAT` |
| 別名 | なし |
| Launch parser の値 | `int8`、`q4_0`、`k8v4`、`fp16`（大文字小文字を区別しない） |

## 役割

会話履歴を保持する KV cache の形式を起動設定に指定します。選んだ値は対応する非 macOS 経路でセットアップへ渡され、生成される engine 引数に反映されます。エンジン側では `fp16`、`int8`、Hadamard 回転後の `q4_0`、INT8 K と Q4_0 V の混合形式 `k8v4` を切り替えます。

## 使い方

```sh
strata launch --model iq3_xxs --context 128k --kv q4_0 --no-tui
```

`--kv` は `strata launch` のモデル起動設定です。ネイティブ engine のトップレベル `--kv` とは別の parser スコープですが、選択値は engine 用設定へ渡されます。

## 値と既定値

- Launch parser は `int8`、`q4_0`、`k8v4`、`fp16` を受け付けます。値は前後の空白を除去して小文字化してから照合します。ほかの値は argparse の型変換エラーとなり、候補一覧（該当時は近い値の提案も）を含む usage エラーになります。
- ただし、非 macOS のセットアップ parser が `--kv` に許可する値は `int8`、`q4_0`、`k8v4` のみです。Launch が受理する `fp16` を明示すると、通常の setup 経路では値が委譲された後に `setup.py` が拒否します。既定の `fp16` は `--kv` を省略して選ぶためこの不一致を通りません。
- `--kv` を省略した場合、LaunchSettings では未指定（`None`）のまま扱われます。Launch の設定表示・比較とセットアップ側の規則では、context が 8,192 token 以下なら `fp16`、それを超える場合は `int8` が選ばれます。したがって Launch オプションの help にある `int8 (default)` は全 context に一律の既定値を意味しません。
- この境界と選択値は `setup.py` にも実装されています。8,192 以下は `fp16`、それを超える場合は `--kv` 指定値または `int8` です。

## 実行時の動作

- parser が受け取った値は `settings_from_args` で起動設定 `s.kv` に設定されます。既存 preset にほかの起動フラグを重ねる場合も、この指定が今回の起動設定に反映されます。
- 非 macOS の通常セットアップでは、値がある場合 `Runner.setup_args()` が `setup.py` に `--kv VALUE` を渡します。`setup.py` は context と値から engine の `--kv` を組み立てます。既存設定との比較・表示では、明示した形式も考慮されます。
- `--save-preset` も指定した場合、起動設定一式が preset として保存されるため、選択した `kv` も保存対象です。preset 起動に一時的な起動フラグを追加しただけなら、明示的な保存をしない限り preset 自体は更新されません。
- macOS では Launch runner が setup に渡す引数を絞り込む際 `--kv` を除外します。したがって、macOS のこの経路では CLI が値を受理しても setup には反映されず、指定値が有効だとは確認できません。
- ネイティブ engine は `--kv` を読み取り、`fp16` / `int8` / `q4_0` / `k8v4` に応じて QSA KV の各モード設定を切り替えます。`q4` は engine 側では `q4_0` に正規化されますが、Launch parser は `q4` を受理しません。

## 適用条件と副作用

- 実際に起動するモデル・engine が対象形式を使うかはモデルや engine 実装に依存します。今回確認した Launch 側は値をセットアップへ渡し、ネイティブ engine は QSA KV mode を切り替えるところまでです。全モデル・全 backend で各形式が使用されることは、この調査では網羅していません。
- セットアップでモデル用設定を生成または更新する起動に作用します。別環境向けに生成済みの設定を単にそのまま使う経路、または macOS の引数フィルター経路での具体的な反映は同一ではありません。
- 明示した形式は context の自動選択より優先します。`setup.py` には、小さいカード向け調整時に context や KV 形式を変更し得る計画処理がありますが、明示した `--kv` を固定条件として渡しています。実機での適合性や性能・品質への影響は測定していません。

## 出力とエラー

- Launch 側で許可されない値を指定すると、`argparse.ArgumentTypeError` により使用法と不正値の説明を出して失敗します（通常の argparse 終了コードは 2）。
- Launch parser を通った `--kv fp16` も、非 macOS で setup.py を実行する経路では setup 側の `choices` に含まれず、setup の usage error（終了コード 2）になります。Launch は setup の失敗を起動失敗として扱います。
- engine に不正な `--kv` が届いた場合は stderr に `strata generate: --kv must be fp16, int8, q4_0 or k8v4` を出して終了コード 2 を返します。Launch が許可する4値は、この engine の検証値と一致します。

## 根拠

- `strata_cli/launch/cmd.py:37-45,95,224-227` — 選択値の正規化・検証、parser 定義、CLI 値から設定への反映。
- `strata_cli/launch/settings.py:31,78-91,272-288` — 選択肢、未指定値、設定表示における値の扱い。
- `strata_cli/launch/runner.py:223-230,264-293` — 既存 config と設定値の比較、KV 値の設定反映。
- `strata_cli/launch/runner.py:727-736,760-774,948-959,997-1012` — setup 起動時の引数転送、macOS での除外、setup.py の呼び出しと非ゼロ終了時の失敗処理。
- `setup.py:8436-8438,9096-9107,9418-9425` — setup parser の許容値（Launch が受け付ける `fp16` は含まない）、context 別既定値、engine 引数生成。
- `src/program/generate.cpp:486-487,2478-2483,3186-3204` — engine の既定値、parser、値検証、KV mode の設定。
- `strata_cli/launch/store.py:75-85`、`strata_cli/launch/cmd.py:788-793` — preset 保存と起動時の明示的な保存処理。
