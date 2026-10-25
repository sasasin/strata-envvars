# `--control-vector`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--control-vector` |
| 別名 | なし |
| 値 | 制御ベクトル形式の GGUF ファイルパスを1つ |

## 役割

GGUF 内の各レイヤー方向ベクトルを、モデルの残差ストリームに適用します。このオプション単独では scale `1.0` の加算モードです。方向ベクトルを射影除去する `project` モードやレイヤー範囲の変更には、関連オプションを併用します。parser は指定されたパスを scale `1.0` と組にして登録します（`src/program/generate.cpp:2702`）。

## 使い方

```sh
strata generate --pack /path/to/pack --tokens "1,2,3" --control-vector /path/to/vector.gguf
```

`--tokens` はエンジンの必須入力の一例です。実際の制御ベクトル適用はモデルのロード後に行われます。

## 値と既定値

- 値は GGUF ファイルパスです。値を省略すると parser が `--control-vector needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:2416-2420`）。
- 複数回指定でき、各ファイルが制御ベクトルの一覧に追加されます。`--control-vector-scaled FILE:SCALE` と併用した場合も同じ一覧に追加され、ロード時に各ファイルの方向へそれぞれの scale を掛けた値を合算します。このオプションから追加したファイルの scale は常に `1.0` です（`src/program/generate.cpp:2702-2716, 1872-1895`）。
- 省略時はベクトルをロードしません。範囲の既定値はレイヤー `1` から最終レイヤーまで、モードの既定値は `add`、方向選択の既定値は `per-layer` です（`src/program/generate.cpp:797-803, 1903-1905`）。

## 実行時の動作

モデル形状の取得後、ファイルを開いて `general.architecture` が `controlvector` であることを確認します。`direction.<layer>` tensor のうちモデルのレイヤー `1` 以上かつ最終レイヤー未満に入るものを使い、要素数が埋め込み次元と一致する f32 でなければ失敗します。レイヤー `0` の方向は使用せず、モデル範囲外のレイヤー tensor は無視します。`controlvector.model_hint` があり `qwen4exp` 以外なら警告しますが、その条件だけでは拒否しません（`src/program/generate.cpp:1872-1901`）。

`--control-vector-layer-range A B` を指定すると適用範囲を両端を含む範囲にします。`--cvec-mode add` では各レイヤーの方向を加算し、`--cvec-mode project` では方向を単位化して射影成分を除きます。`--cvec-dir single:L` は `project` モードでレイヤー `L` の方向を範囲内の各レイヤーに使います。いずれも指定可能な値と相互作用は別オプションの parser に定義されています（`src/program/generate.cpp:2718-2732, 1903-1930`）。

制御ベクトルはレイヤーの FFN write 後に各 residual stream へ適用されます（`include/strata/kernels/cvec.hpp:5-16, 59-63`; `src/core/layer.cpp:1615-1626`）。prompt prefill 経路にも同じ適用があり、条件を満たす場合は write・ベクトル適用・次の norm を一つの kernel に融合します（`src/prefill/prefill.cpp:4813-4823, 4863-4875`）。通常の `generate` ではロード後に有効になります。`--serve` ではリクエストごとの `cvec=0|1` で切り替えられ、省略時は有効です（`src/program/generate.cpp:12304, 12338, 12520, 12922-12927`）。

## 適用条件と副作用

- 有効化には少なくとも1つのロード可能な方向 tensor が、指定（または既定）のレイヤー範囲内に必要です。範囲外の tensor はロードされても適用対象になりません（`src/program/generate.cpp:1884-1888, 1912-1929`）。
- マルチ GPU の layer split について、ソース内の説明には不一致があります。制御ベクトルは GPU 間で未対応とのコメントがある一方（`src/program/generate.cpp:2969-2974`）、split stage の作成時に表を複製する処理もあります（`src/program/generate.cpp:4368-4370`）。このため、この組み合わせの実際の適用可否はソース確認だけでは確定できません。
- Metal は未対応です。Metal の `cvec_upload` は未実装 entry point の stub で、既定では stderr に未対応関数名を出して終了コード `86` でプロセスを終了します（`metal/src/engine/stubs.cpp:185`; `metal/src/engine/missing.cpp:1-23, 32-40`）。Mac 向け資料も control vector が未移植としています（`docs/MAC.md:257`）。
- 制御ベクトルをロードした状態は session identity に含まれるため、保存 session はロード済みベクトルの内容・mode・範囲と結び付けられます（`src/program/generate.cpp:1863-1866, 1932-1940`）。

## 出力とエラー

有効なベクトルを読み込むと、stderr に mode、方向選択、対象レイヤー範囲、適用できるレイヤー数を出力します（`src/program/generate.cpp:1942-1946`）。architecture 不一致、方向 tensor の型・サイズ不一致、方向 tensor がない、適用範囲に方向がない、またはファイル読み込み例外がある場合は、`strata generate: control vector: ...` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:1874-1900, 1929, 3963-3968`）。

## 根拠

- 索引はこの項目を `strata-engine` の root scope に配置しています（`docs/cli/README.md:1128-1148`）。エンジンの利用形は parser の usage に `strata generate ...` と記載されています（`src/program/generate.cpp:806-808`）。
- parser 定義、既定値、補助 option は `src/program/generate.cpp:797-803, 953-957, 2702-2732`。
- GGUF の検査、合成、upload、session identity は `src/program/generate.cpp:1863-1947`。
- 適用位置と per-request 切り替えは `include/strata/kernels/cvec.hpp:5-16, 50-63`, `src/core/layer.cpp:1615-1629`, `src/prefill/prefill.cpp:4813-4823, 4863-4875`, `src/program/generate.cpp:12304-12338, 12520, 12922-12927`。

## 調査範囲

同一 revision のソースを確認しました。安全に実行できる同一 revision の既存 engine help は確認できなかったため実行していません。Qwen3.6 のモデル family は `src/program/generate.cpp:2393-2407` で別実装へ分岐しますが、その実装がこのオプションに与える挙動は本調査では確定していません。配布済み Release artifact ごとの対応 backend も確認していません。
