# `strata update --backend`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend family 名。`hip-rdna2` のように HIP の variant を付けて指定する形式も処理される |

## 役割

エンジン更新時に、GPU 自動検出の代わりに対象 backend family を選びます。HIP の `--backend hip-rdna2` のような指定では、family を `hip`、variant を `rdna2` として扱います。オプションはエンジン package の選択に使われ、Control や desktop app の更新先を選ぶものではありません。

## 使い方

```sh
# HIP 系エンジンの候補を確認する（feed の読み込みは行うが、package はダウンロードしない）
strata update --backend hip-rdna2 --check

# 指定した backend のエンジンを含めて通常の更新を行う
strata update --backend cuda
```

## 値と既定値

parser は `--backend` に文字列値を取り、既定値は `None` です。`choices` や型変換による parser 段階の制限はありません。省略時は検出した hardware/backend を使います。値が空文字列の場合も `if a.backend` の条件に入らず、指定なしと同じ扱いです。空白だけの文字列は truthy なので override され、`split_backend` 内で trim 後に空となります。

指定値は trim して小文字化されます。`hip-` で始まり後続文字がある文字列は `hip` と suffix に分割されます。`hip-` の後ろが空の場合や、その他の名前はそのまま backend family として使用されます。`BACKEND_MATRIX` にある family は `metal`、`cuda`、`hip`、`sycl`、`cpu` ですが、`--backend` 自体はこの集合への validation を行いません。未知の family 名は parser では拒否されず、feed 内の engine package と一致しなければ選択候補がなくなります。

## 実行時の動作

`run()` はまず `updater.detect_hardware()` で platform、GPU 情報、backend などを調べます。`--backend` が truthy の場合、検出結果の `backend` を指定 family に置き換え、`backend_source` を `requested` にします。分割された variant があれば `variant_wanted` にも設定します。この `requested` 印は GPU make の保護判定に明示指定として渡ります。`--backend` を省略すると、`STRATA_ENGINE_BACKEND` を含む通常の検出結果が使われます。CLI 指定がある場合は、その結果を後から上書きします。

feed の engine package は platform と family が一致し、runtime・CUDA/HIP architecture・NVIDIA driver の適合条件も満たすものに絞られます。同じ family の候補から version などで選びます。HIP の variant 指定が選択に効くのは、HIP architecture (`gfx`) を検出できず、複数 variant が候補に残る場合です。その場合は指定 variant、GPU 名からの推定、既設 variant の順に選択します。architecture を検出できた場合は variant の指定より architecture の適合判定が先に効きます。

## 適用条件と副作用

- `--check` でも指定値は package 選択に適用され、結果に engine 候補と hardware 情報が出ます。check は feed を読み、更新結果を component state の `last_check` に保存しますが、feed 外の package はダウンロードしません。
- 通常更新では選ばれた engine package の取得・検証・test start・切替に進みます。`--backend` は engine のみを制御し、通常の `strata update` が行う Control 更新や、`--app` を付けた場合の app installer 取得には適用されません。
- 別 backend family を明示した場合、インストール済み engine と異なる GPU make でも自動選択時の make guard を通過します。この指定は適合性を保証しません。platform、architecture、driver などの適合理由により該当 package が選ばれないことがあります。
- 未知の family 名や feed にない variant は parser でエラーになりません。候補がなく `--check` ならその状態を表示して終了し、通常更新では engine は「この PC 向け package なし」となり、その経路だけなら変更せず終了します。他の指定がなければ Control など別 component の更新は続きます。未知 family に対する独立した validation error は実装上確認できません。

## 出力とエラー

人向け出力は `--check` で選択結果・選ばれなかった理由を表示し、通常更新では component ごとの結果を表示します。`--output json` / `jsonl` も同じ hardware 選択を使います。更新処理で `UpdateError`、feed 読み込みで `FeedError`、署名検証で `SignatureError` などが起きると、通常出力では `strata: ...` を stderr に出し、例外に応じた終了 code を返します。`--backend` の任意文字列そのものを検証する専用エラー経路はありません。

## 根拠

- `strata_cli/update_cmd.py:37-46,49-56` — `--backend` parser 定義、既定値、update parser への登録。
- `strata_cli/cli.py:139-140,2135-2137` — update parser の登録と `update_cmd.run()` への dispatch。
- `strata_cli/update_cmd.py:194-206` — 検出した hardware への CLI 指定の反映と実行 context の生成。
- `strata_control/engine_component.py:439-445` — backend 名の正規化と `hip-<variant>` の分割。
- `strata_control/targets.py:20-29` — backend family と対応 platform の matrix。
- `strata_control/updater.py:255-275,546-570,573-582` — hardware 検出結果、明示選択時の make guard、feed package 選択への接続。
- `strata_control/feed.py:408-431,434-461,468-495` — platform/family/architecture/driver の適合判定、候補選択、HIP variant 選択条件。
- `strata_control/updater.py:631-647,1038-1063,1466-1489` — check の state 保存、通常更新の engine 選択と処理、component 単位の結果・終了 code。
