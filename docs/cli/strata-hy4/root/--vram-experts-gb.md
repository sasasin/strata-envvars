# `--vram-experts-gb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--vram-experts-gb` |
| 別名 | なし |
| 値 | 浮動小数点数として `atof` で変換。単位は GiB 相当（値に 1,073,741,824 を乗算） |

## 役割

expert weights を GPU メモリに置く量の上限を指定します。全 expert weights の必要量や空き VRAM がこの上限を超える場合、GPU に配置する expert の枠を縮小し、残りは通常の tiered loading に委ねます。単一 GPU では GPU expert budget の上限、複数 GPU では選択 GPU 全体に対する合計上限として働きます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:145`, `:937-952`, `:1420-1434`）。

## 使い方

```sh
strata-hy4 --model model.strata --tokens ids.txt --vram-experts-gb 8
```

`--serve` でも同じ値がモデルロード設定に渡されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:451-454`, `:555-577`）。

## 値と既定値

- 既定値は `-1.0` で、0未満の値は上限を適用しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:367`, `engine/src/hy4flash/run/hy4_gpu_model.hip.h:145`, `:937`）。
- `0` は有効な上限で、expert 用 VRAM 枠を0にします。
- `atof` で変換するだけで、数値形式や非負範囲の明示的 validation はありません。変換できない文字列は `atof` の結果として0になり、上限0として扱われます。数値の後ろに余分な文字がある場合などの厳密な拒否も実装されていません（`engine/src/hy4flash/run/hy4_main.hip.cpp:451-454`）。
- 同じオプションを複数回指定すると、引数走査中に同じ変数へ順次代入されるため最後の値が使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384`, `:451-454`）。
- 値を省略すると parser の `nxt()` が `ERR --vram-experts-gb needs a value` を stdout に出し、終了コード2で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382`, `:451-453`）。

## 実行時の動作

parser は値を `double` に変換し、通常実行では `GpuModel::vram_experts_gb_cap` に設定します。`--serve` 経路でも `ServeOpts` に格納し、serve 側で同じ `GpuModel` フィールドに渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:451-454`, `:649-656`, `:555-577`, `engine/src/hy4flash/run/hy4_serve.hip.h:268-276`）。

expert の読み込み時、各 GPU の空きメモリ等から計算した VRAM 枠の合計が指定上限を超える場合、上限をバイトに換算し、各 GPU の枠を元の枠に比例して縮小します。換算には 1 GiB = 1,073,741,824 bytes を使います。したがって値は厳密な実使用量保証ではなく、expert 配置枠の上限です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:876-895`, `:937-952`）。

単一 GPU では通常、空き VRAM から `HY4_RESERVE_GB`（未設定時6 GiB）を引いた値が基礎 budget です。`HY4_EXPERT_VRAM_GB`、なければ `STRATA_HY4_VRAM_GB` が設定されていると基礎 budget をその値に置き換え、その後このオプションの上限との小さい方を採用します。複数 GPU では各 GPU の枠を計算した後、合計が上限を超える場合に比例縮小します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1434`, `:937-952`）。

## 適用条件と副作用

- `--vram-experts-gb` が0以上で、計算済み GPU 枠の合計が指定値を超えた場合に比例縮小と適用ログ出力が発生します。合計が上限以下ならこの処理は変更を加えず、適用ログも出しません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:937-952`）。
- 1 GPU ではフル expert section が budget 内に収まれば全体を GPU にロードします。収まらなければ tiered loading に入り、VRAM 枠と host RAM 枠に応じて配置されます。オプションによる枠縮小だけでロード失敗が決まるわけではありません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1503`）。
- 多 GPU では縮小後の枠が expert の GPU 配置判断に使われます。`--layer-split auto` も縮小後の VRAM 枠を GPU 間の重み付けに使います（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:954-970`, `:1013-1035`）。
- 実際のモデル読み込みでGPU/runtime割り当てに失敗した場合、ロード側がエラーを stderr に出して失敗を返し、通常実行は終了コード1になります（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1499-1502`, `engine/src/hy4flash/run/hy4_main.hip.cpp:658-660`）。このオプション自体に独立したファイル書き込み等の副作用は確認できません。

## 出力とエラー

上限により枠を縮小したとき、stderr に `[load] --vram-experts-gb ... cap applied across ... GPU(s): GPU...<=...GiB` を出します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:946-951`）。上限値の範囲検証エラーや、負数値に対する警告はありません。値の欠落時は stdout のエラーと終了コード2、未知のオプション文字列は stderr の `unknown arg ...` と終了コード2になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382`, `:498-505`）。

## 根拠

- parser の既定値と値の取り込み: `engine/src/hy4flash/run/hy4_main.hip.cpp:367`, `:377-384`, `:451-454`
- 通常実行・serve への設定伝播: `engine/src/hy4flash/run/hy4_main.hip.cpp:555-577`, `:649-656`; `engine/src/hy4flash/run/hy4_serve.hip.h:268-276`
- 複数 GPU 枠の準備と合計上限の按分: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:876-895`, `:937-952`
- 単一 GPU budget、環境変数との相互作用、全体ロード/tiered loading: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1503`
- 適用後の自動 layer split と配置: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:954-970`, `:1013-1035`

