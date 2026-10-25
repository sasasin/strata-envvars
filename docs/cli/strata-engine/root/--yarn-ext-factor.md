# `--yarn-ext-factor`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--yarn-ext-factor` |
| 別名 | なし |
| 値 | 数値 `F`（有限値で `F >= -1`） |

## 役割

RoPE の YaRN 補正に使う extension factor を指定します。YaRN では角度を補間値と学習時の外挿値の間で周波数ごとに混ぜる係数となり、`0` はその角度混合を無効にします。このオプションは単独で RoPE scaling の種類を YaRN に切り替えません。種類は `--rope-scaling` またはモデルの GGUF メタデータで決まり、未指定時の `-1` は種類に応じた自動値を選びます（`src/program/generate.cpp:450-463, 3315-3327, 3703-3707`）。

## 使い方

```sh
strata --pack MODEL-PACK --ple-gguf PLE.gguf --tokens 1,2,3 --yarn-ext-factor 0.5
```

YaRN を明示して使う例:

```sh
strata --pack MODEL-PACK --ple-gguf PLE.gguf --tokens 1,2,3 --rope-scaling yarn --yarn-ext-factor 0.5
```

`MODEL-PACK`、`PLE.gguf`、トークン列は実際のモデル構成に合わせてください。エンジンの usage は `strata` の最上位引数としてこのオプションを列挙しています（`src/program/generate.cpp:867-877`）。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。省略時の内部値は `-1.0` です。`-1` は自動指定を意味し、負の値は `-1` 以上だけ受理されます（`src/program/generate.cpp:460, 2451, 3345-3349`）。
- `--yarn-ext-factor` の後に値がない場合、parser の `next()` が `stderr` に `--yarn-ext-factor needs a value` を出し、終了コード `2` で終了します（`src/program/generate.cpp:2416-2420, 2451`）。
- NaN / 無限大は有限値チェックで拒否されます。`F < -1` も「invalid rope scaling knob」として拒否されます（`src/program/generate.cpp:3328-3334, 3345-3349`）。
- `atof` の戻り値だけを使い、変換末尾や変換失敗を別途検査する処理はありません。そのため数値として読めない文字列は C ライブラリの変換結果（通常 `0`）になり得ます。コードが文字列全体を厳密な数値形式として検証するわけではありません（`src/program/generate.cpp:2451`）。
- 同じオプションを複数回指定した場合、parser ループで後の値が同じフィールドに再代入されるため、最後の指定が残ります（`src/program/generate.cpp:2416-2420, 2451`）。

## 実行時の動作

- 解決時に `F >= 0` なら指定値を `rope_cfg.ext_factor` に設定します。`F < 0`（受理される範囲では `-1`）なら、RoPE 種類が YaRN のとき `1.0`、それ以外では `0.0` が選ばれます。したがって未指定の既定値 `-1` は YaRN で自動有効、それ以外では自動無効です（`src/program/generate.cpp:3703-3704`）。
- RoPE 種類は `--rope-scaling none|linear|yarn` が明示されればその値を使い、未指定ならモデルの `rope.scaling.type` を読みます。明示した値はモデルメタデータより優先されます（`src/program/generate.cpp:3315-3327, 3682-3694`）。
- `linear` または `yarn` の scaling が有効な場合、RoPE table builder は `ext_factor != 0` のときに限って各周波数の角度を補間角と学習時角度の ramp 混合にします。値 `0` は角度混合を無効にし、値 `1` は ramp 全体を使います（`src/kernels/cuda/rope.cu:61-83`）。この係数だけから性能向上を断定できる根拠はありません。
- scaling 種類が `none` の場合、RoPE scaling knob はリセットされて適用されません。`F > 0` など明示的な knob がある場合は「no rope scaling is active (none)」という注意が `stderr` に出ます。`F=0` や未指定の `-1` だけでは、この注意判定に `--yarn-ext-factor` は該当しません（`src/program/generate.cpp:3708-3719`）。
- 解決済み RoPE 設定は `rope_scaling_set()` に渡され、session 初期化より前に固定されます。ソースコメントは RoPE 後の K が cache に入るため実行中の要求ごとに切り替えない設計としています（`src/program/generate.cpp:450-454, 3731-3738`）。
- `--model` または `--native` で Qwen3.6 GGUF が検出されると、通常 parser に入る前に `strata::qwen35::run(argc, argv)` へ全引数が渡されます。この文書の通常 engine parser による受理・動作説明を、その別 parser にも適用できるかは確認していません（`src/program/generate.cpp:2393-2407`）。

## 適用条件と副作用

- YaRN の自動値 `1.0` は `--yarn-ext-factor` を指定しない場合の値です。linear scaling で YaRN knob を明示的に使用したい場合は、`--yarn-ext-factor` に非負値を渡してください。`--rope-scaling none` では値は実質無効です（`src/program/generate.cpp:3703-3719`）。
- 値は起動時に一度解決され、RoPE table / kernel 設定に反映されます。動的な変更用の per-request 引数はありません（`src/program/generate.cpp:450-454, 3731-3738`）。
- ソース上でこの値に伴うファイル書き込みやネットワークアクセスは確認できません。主な副作用は実行時の RoPE 角度計算への反映と、設定ログ・注意メッセージの `stderr` 出力です（`src/program/generate.cpp:3731-3749, src/kernels/cuda/rope.cu:61-83`）。

## 出力とエラー

- 不足値、非有限値、または `F < -1` は終了コード `2` となります。不足値および validation message は `stderr` 出力です（`src/program/generate.cpp:2416-2420, 3328-3334, 3345-3349`）。
- `--rope-scaling none` と正の `--yarn-ext-factor` を併用すると、値は適用されず、`stderr` に scaling knob が無効である旨の note が出ます（`src/program/generate.cpp:3708-3719`）。
- 有効な scaling の解決時には種類、factor、frequency scale、base、mscale、trained context と `--max-context` が `stderr` に記録されます（`src/program/generate.cpp:3731-3743`）。

## 根拠

- parser の値格納と欠落値処理: `src/program/generate.cpp:2416-2420, 2451`
- 既定値・help 表示: `src/program/generate.cpp:450-463, 867-877`
- validation: `src/program/generate.cpp:3312-3350`
- モデル設定との優先順位、YaRN 自動値、none 時の扱い、設定反映とログ: `src/program/generate.cpp:3682-3749`
- 角度 ramp 混合への利用: `src/kernels/cuda/rope.cu:61-83`
- Qwen3.6 専用 parser への early dispatch: `src/program/generate.cpp:2393-2407`

同一 revision の実行バイナリの `--help` は実行していません。ソース内の usage 文字列と parser 定義を照合しました。GPU / backend ごとの実行時差は、この読み取り調査では実測していません。
