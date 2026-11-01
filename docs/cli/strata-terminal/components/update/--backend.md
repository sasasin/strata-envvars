# `strata components update --backend`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | 文字列。parser では選択肢を検証しない。バックエンド名、または HIP の場合は `hip-<variant>` を指定する |

## 役割

この PC の GPU から自動判定する代わりに、更新フィードから選ぶ engine のバックエンド family を指定します。`strata update` も同じ `_common()` parser を使い、同じ処理へ委譲されます。`strata components update` は engine と Control の更新を行い、`--backend` が指定するのは engine package の選択条件です（`strata_cli/update_cmd.py:37-63,183-205`）。

## 使い方

```sh
strata components update --backend cuda --check
strata components update --backend hip-rdna2
```

`--check` を付ける例は feed を確認して選択結果を表示するだけで、engine package はダウンロードしません。2つ目は通常の更新処理を実行します（`strata_cli/update_cmd.py:235-245`）。

## 値と既定値

- 省略時は `updater.detect_hardware()` の検出結果を使います。既定値を parser に固定指定しているわけではありません（`strata_cli/update_cmd.py:40,195-201`、`strata_control/updater.py:255-275`）。
- `--backend` は `choices` や `type` を持たない文字列引数です。指定時は `split_backend()` が前後空白を除き、小文字化します。`metal`、`cuda`、`hip`、`sycl`、`cpu` は backend family 名です。これらの OS 対応範囲は `strata_control/targets.py:23-29` に定義されていますが、この CLI 引数自体はその組み合わせを事前検証しません（`strata_cli/update_cmd.py:40,197-201`、`strata_control/engine_component.py:439-445`）。
- `hip-rdna2` のように `hip-` で始まり後続文字がある値は、family `hip` と variant `rdna2` に分割されます。`hip-` だけでは variant に分割されず、その文字列全体が backend として渡ります（`strata_control/engine_component.py:439-445`）。
- 空文字列を値として渡した場合は `if a.backend` が偽となり、検出結果を上書きしません。空白だけの値は truthy なので上書き処理に入り、正規化後の backend は空文字列です。重複指定時は `argparse` の通常の単一値引数として最後の値が残ります（`strata_cli/update_cmd.py:40,197-201`、`strata_control/engine_component.py:442-445`）。

## 実行時の動作

指定が truthy なら、検出済み hardware 情報の `backend` を指定値に置き換え、HIP variant があれば `variant_wanted` に入れ、`backend_source` を `requested` にします。検出時に集めた platform、GPU 名、architecture 等の情報を再取得・消去する処理はありません（`strata_cli/update_cmd.py:195-205`、`strata_control/updater.py:255-275`）。

`STRATA_ENGINE_BACKEND` はこの上書きより先に `detect_hardware()` が読みます。その環境変数が無効値なら、明示的な `--backend` があっても hardware 検出時に失敗します。また環境変数で `hip-<variant>` を指定し、CLI では `--backend hip` とした場合、CLI 側は variant を空に戻さないため、環境変数由来の `variant_wanted` が残ります（`strata_control/updater.py:255-275`、`strata_control/engine_component.py:448-456`、`strata_cli/update_cmd.py:195-201`）。環境変数自体の詳細は [`STRATA_ENGINE_BACKEND`](../../../../envvars/STRATA_ENGINE_BACKEND.md) を参照してください。

この hardware 情報は、まず現在の engine と指定 backend の異なる GPU make を維持・拒否する guard に渡り、その後 feed の package 適合判定・選択に使われます。`cuda`、`hip`、`sycl` の異なる make の engine が既にあり、指定先の make が検出済み GPU にない場合、明示指定は guard を通過させるため、実際に切り替えを試みます。選択された package の test-start が失敗すれば更新は確定せず、旧 engine が維持されます（`strata_control/updater.py:546-582,1040-1065,1068-1096`）。

`hip-<variant>` の variant 指定が package 選択の優先条件になるのは、HIP と判定され、検出した AMD `gfx` が空で、異なる HIP variant の package が複数候補に残る場合です。その場合、指定 variant と一致する package を優先します。`gfx` が検出済みなら architecture 適合性で候補を絞るため、この variant 指定はその分岐では使われません。複数候補が残り指定 variant に一致するものがない場合は、GPU 名、インストール済み variant の順に判定し、それらでも決まらなければ HIP package を選ばない経路があります（`strata_control/feed.py:408-431,434-461,468-495`）。

`--check` は同じ hardware 条件で選択内容を報告しますが、`run_update()` には進みません。通常更新では選択結果に従って engine 更新が試みられます。`--no-engine` を併用すると engine 更新を無効化できるため、`--backend` を指定しても engine package の更新は行われません（`strata_cli/update_cmd.py:235-256`）。

## 適用条件と副作用

- 指定値に一致する platform / backend / architecture / driver 条件の feed package がない場合、engine は `none-for-this-pc` となり、選択理由が報告されます。`--backend` の値自体を parser が拒否するのではなく、package 選択で適合候補がなくなる形です（`strata_control/feed.py:408-431`、`strata_control/updater.py:573-601`）。
- 通常の更新では feed の読み込み、package 選択に続き、engine package のダウンロード、検証、staging、test-start、切り替えが起こり得ます。成功時は直前の engine を保持し、次回起動から新 engine を使用します（`strata_control/updater.py:1038-1065,1068-1149`）。
- `backend_source=requested` は make guard の例外条件です。誤った family を明示すると GPU に合わない package を試す可能性があります。feed の署名・package 検証や test-start は別途実行され、失敗時は通常の拒否・失敗経路に入ります（`strata_control/updater.py:546-570,1051-1065`）。
- OS ごとの対応表は存在しますが、CLI の `--backend` parser による OS/backend 組み合わせの事前拒否は確認できません。feed に適合 package がなければ選択できません（`strata_control/targets.py:20-29`、`strata_cli/update_cmd.py:37-46`）。

## 出力とエラー

値の不正を理由にした専用 parser validation はありません。通常の人向け出力では `--check` が選択 engine と不適合理由を表示し、更新実行時には engine の状態を表示します。`--output json` / `jsonl` では機械可読出力になります（`strata_cli/update_cmd.py:37-46,72-94,152-181,235-256`）。

feed に候補がない場合は選択不能の報告となり、単独で parser error にはなりません。署名・feed・update error は stderr の `strata: ...`（human）または JSON error に変換されます。例として、engine の切り替え後に新 engine が選ばれない場合は exit code 6 で失敗し、旧 engine は変更されません（`strata_cli/update_cmd.py:187-192,257-266`、`strata_control/updater.py:1117-1129`）。

## 根拠

- parser 定義と共通適用範囲: `strata_cli/update_cmd.py:37-69`
- 値の上書きと handler の dispatch: `strata_cli/update_cmd.py:183-205`、`strata_cli/cli.py:139-140,2135-2137`
- 自動検出情報と override の対象: `strata_control/updater.py:255-275`
- family / HIP variant 正規化: `strata_control/engine_component.py:439-445`
- make guard と feed 選択への伝播: `strata_control/updater.py:546-621`
- package 適合条件と HIP variant の選択: `strata_control/feed.py:408-431,434-495`
- 更新・test-start・切り替え失敗時の経路: `strata_control/updater.py:1038-1065,1068-1149`
- 調査制約: ソース checkout の parser と処理経路を根拠とし、別途ビルドされた CLI help、Release archive の実体、各 OS / GPU 上の実行結果は確認していません。
