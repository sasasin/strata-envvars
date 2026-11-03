# `STRATA_DS4_DISK_SKIP_SETTLE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`STRATA_DS4_DISK_SKIP_AUTO` が使う「ディスク読み飛ばし」の自動停止判定で、cold share が改善しなくなった後、停止するまでに必要な token 数を指定します。単独ではディスク読み飛ばしを有効にしません。自動モードが有効なとき、設定した settle token 数が `no longer falling` の停止条件に使われます。

## 値と判定

読み取りは `ds4_model.cu` の `env_f` helper を経由します。環境変数が未設定なら既定値 `64.0f`、設定されていれば `std::atof` で float に変換し、`int` にキャストした後 `std::max(4, ...)` で下限を 4 にします。したがって空文字や数値に変換できない文字列は `atof` の結果 0 から 4 になり、負値も整数化後に 4 へ clamp されます。4 未満の正値も整数化後に 4 です。小数は `int` への変換で小数部分を落とします。文字列全体の厳密な検証、上限 clamp、無効値のエラー出力はありません。

| 環境値 | `disk_skip_settle` |
|---|---:|
| 未設定 | 64 |
| 空文字、非数値文字列、0、負値、4 未満 | 4 |
| `4` 以上の有限数値 | 小数部分を落とした整数値 |

`atof` が認識する数値部分の後ろに文字がある場合も、helper は変換エラーを検査しません。たとえば `12tail` は 12 として扱われます。値を整数にした後の上限検査はありません。

## 有効になる条件

- 値の読み取りと自動停止ロジックは `src/dsv41/ds4_model.cu` の DSV41 モデル実装にあります。
- settle 閾値は `STRATA_DS4_DISK_SKIP_AUTO` が非ゼロで、かつ `STRATA_DS4_DISK_SKIP_W` が正のときにだけ使われます。`DISK_SKIP_AUTO` が無効、または `DISK_SKIP_W` が 0 以下なら `skip_auto_tick` による settle 判定は実行されません。
- `STRATA_DS4_DISK_SKIP_AUTO` が有効でも、先に自動停止 budget 到達または cold share 2% 以下の条件を満たせば、settle 閾値より前に停止します。観測窓が満たされない場合も settle 条件は評価されません。
- CLI 引数や設定ファイルによるこの値の上書きは、対象ソース内では確認できません。

## 実行時の詳細

値は `Model::Impl` のメンバー初期化時に通常の `const int` として読み取られ、そのモデルインスタンス内で保持されます。`static` cache ではありませんが、各 `skip_auto_tick` 呼び出しで環境を再読することもありません。実行中に環境値を変更しても、すでに作られたモデルの閾値は変わりません。

自動モードの統計は `disk_skip_from` の layer に到達したとき token 数を進めます。直近の `STRATA_DS4_DISK_SKIP_WINDOW` 分の層・token を集計し、観測窓が埋まり cold share の最低値から 5% 以上改善する状態が `disk_skip_settle` token 続いた場合、読み飛ばしを停止します。停止時は stderr に `ds4: DISK_SKIP auto: off after ... tokens (no longer falling; cold share ..., the lowest ...)` が出ます。これは自動停止条件の閾値であり、ディスク読み飛ばし自体の重み条件や読み飛ばす対象は `STRATA_DS4_DISK_SKIP_W` 側で制御されます。

## 根拠

- `src/dsv41/ds4_model.cu:1352` — `env_f` は unset 時に既定値を返し、設定時は `std::atof` を使う。
- `src/dsv41/ds4_model.cu:1391-1400` — `STRATA_DS4_DISK_SKIP_W` の既定値と非負 clamp。
- `src/dsv41/ds4_model.cu:1441-1445` — 自動モード条件、 settle の既定値 64、下限 4、他の自動停止閾値。
- `src/dsv41/ds4_model.cu:1464-1488` — stderr 停止ログ、集計と budget / 2% / settle 判定。
- `src/dsv41/ds4_model.cu:9463-9464,9511` — 自動モードが on のときだけ統計更新・自動停止判定を呼び出す。
- `000_envvers.md` に候補名があることは確認した。`docs/DETAILS.md` にはこの変数に関する説明を確認できなかった。
