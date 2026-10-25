# `strata tune plan --time`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--time` |
| 別名 | なし |
| 値 | 秒単位の浮動小数点数（省略時 `1800.0`） |

## 役割

計画に記録して表示する、探索の総時間上限を指定する。`tune plan` は探索を実行せず、この値を計画の `total_time_s` に入れて表示する。実際に探索を行う `strata tune run` にも同名のオプションがあり、そこでは同じ値が新しい候補試行を始める時間上限として使われる。

## 使い方

```sh
strata tune plan --engine /path/to/strata --backend cuda --model my-model --time 900
```

`--engine`、`--backend`、`--model` は `tune plan` で必須。`--time` は秒数を指定し、省略すると 1800 秒（30 分）が計画に使われる。

## 値と既定値

- parser は `float` に変換し、属性 `total_time` に格納する。既定値は `1800.0` 秒。単位や既定値は parser の定義による（`strata_cli/cli.py:398-407`）。
- `tune plan` から呼ばれる計画関数は `total_time_s` を `float` に変換して保存するが、正の値かどうかなどの範囲検証はしていない（`strata_cli/cli.py:1715-1721`、`strata_control/tuning.py:723-767`）。したがって負数や 0 も計画値として受け付けられる。負数を計画表示に指定しても計画作成時の候補探索は行われない。
- 数値に変換できない値は argparse の型変換エラーとなり、usage とエラーを表示して終了コード 2 になる（parser 定義: `strata_cli/cli.py:406-407`、引数解析: `strata_cli/cli.py:2223-2231`）。
- Python の `float` が受理する `nan` や `inf` も parser では明示的に拒否されない。人間向け出力は秒数を小数点以下 0 桁で表示する。JSON 出力では非有限値を拒否するシリアライザーを使うため、計画 JSON の出力時に値エラーとなり、共通エラー処理を通る（`strata_cli/cli.py:1722-1727`、`strata_cli/cli.py:535-542`、`strata_cli/cli.py:2166-2173`）。

## 実行時の動作

`--time` の値は `tuning.plan_tuning(..., total_time_s=...)` に渡され、計画オブジェクトの `total_time_s` として保持される。人間向け出力では `bounds` 行に `秒 total` として表示され、`--output json` では計画データに含まれる（`strata_cli/cli.py:1715-1727`、`strata_control/tuning.py:762-767`）。

`tune plan` は計画内容・探索可能な次元・除外理由を示して終了し、時間値を使ったベンチマークや探索試行は行わない（`strata_cli/cli.py:1632-1638`、`strata_cli/cli.py:1722-1739`）。ただし計画生成時にエンジンの option 一覧を照合するため、指定エンジンを `--help` 付きで起動する。実行は最大 20 秒で、標準出力と標準エラーを読み取る。起動に失敗した場合は一覧を取得できなかったものとして静的表を使う（`strata_control/tuning.py:205-224`、`strata_control/tuning.py:729-735`）。

同じ `--time` は `strata tune run` にも定義され、そちらでは計画へ渡された時間を使ってベースライン測定後の候補探索を制限する。経過時間が上限を超えた時点で新しい候補の開始を止め、既に開始した候補の中断を保証する設定ではない（`strata_cli/cli.py:423-424`、`strata_cli/cli.py:1763-1768`、`strata_control/tuning.py:439-455`）。この別コマンドでの実際の経過時間制御は `tune plan --time` 自体の実行には適用されない。

## 適用条件と副作用

時間値は `tune plan` の計画表示・計画データに適用される。コマンド自体は active profile を変更せず、チューニング結果を適用する処理も呼ばない（`strata_cli/cli.py:1722-1739`）。別途、エンジン `--help` の子プロセス起動と、計画の比較 identity を作るための engine ファイル情報の取得が行われる（`strata_control/tuning.py:205-224,753-767`）。

`--engine component:strata-engine` 形式では、対象 backend の engine package 参照を解決する。該当 engine が見つからない場合は `ProfileError`（終了コード 5）となる（`strata_cli/cli.py:1621-1629`）。通常のパスを指定した場合、plan 経路では存在確認を先に行わず、エンジン起動に失敗すれば flag 一覧不明として計画を続ける（`strata_cli/cli.py:1715-1721`、`strata_control/tuning.py:205-224`）。

## 出力とエラー

- 既定の人間向け出力では `bounds    at most <試行数> trials, <秒数>s total` の行に値が表示され、正常終了は 0（`strata_cli/cli.py:1724-1739`）。
- `--output json` は成功時に `plan.total_time_s` を含む JSON を stdout に出す。非有限の時間値は JSON serializer が拒否し、共通 `ValueError` 経路からエラー JSON（終了コード 2）になる（`strata_cli/cli.py:1722-1723`、`strata_cli/cli.py:535-542,2166-2173`）。
- 数値でない値は argparse が usage とエラーを stderr に出し、コード 2 で終了する。値そのものに対する独自の範囲エラーメッセージは定義されていない（`strata_cli/cli.py:406-407,2223-2231`）。

## 根拠

- parser、型、既定値、help: `strata_cli/cli.py:398-412`。
- `tune plan` から計画関数への引き渡しと human/JSON 出力: `strata_cli/cli.py:1715-1739`。
- 計画関数の文書化された境界と値の保存: `strata_control/tuning.py:723-767`。
- エンジン flag 照合の子プロセス・timeout・fallback: `strata_control/tuning.py:205-224,729-735`。
- `tune run` における時間値の候補開始制限: `strata_cli/cli.py:423-424,1763-1768`、`strata_control/tuning.py:439-455`。
- 索引での command path と予定リンク: `docs/cli/README.md:726-739`。

調査時の `git status --short --branch` は `## main...origin/main` で、未コミット変更は表示されなかった。CLI help の実行、build、GPU 実行、性能測定、テストは行っていない。
