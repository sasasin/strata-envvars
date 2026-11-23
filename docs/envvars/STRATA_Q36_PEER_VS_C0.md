# `STRATA_Q36_PEER_VS_C0`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 の hybrid expert 配置で、第二 GPU の peer tier に card 0 側にも常駐する expert を置き、両 GPU が同じ `(layer, expert)` の routed row を計算できるようにする診断用スイッチです。該当する重複 row は peer の出力と card 0 の出力を float 値で比較し、差分数と最大絶対差を stderr に記録します。通常の peer tier では card 0 の slot を優先して重複計算を避けますが、この設定があると peer にも存在する card 0 slot の entry を peer に割り当てます（`engine/src/qwen35/q36_engine.cu:3216-3221,4387-4392`）。

比較用の値は診断処理に使われ、比較結果で生成処理を中断する分岐はありません。peer が返した row は通常どおり merge 用の `cpu_out` として使われます。この設定は配置と実行経路を変えるため、生成結果が不変であることまではコードから保証できません（`engine/src/qwen35/q36_engine.cu:3325-3349,3364-3401`）。

## 値と判定

値の内容は parse されず、`std::getenv(...) != nullptr` という設定有無だけで判定されます。したがって未設定なら無効、空文字を含む何らかの値が設定されていれば有効です。`0`、`false`、大文字小文字、空白、数値としての妥当性に特別な意味はありません（`engine/src/qwen35/q36_engine.cu:3210,3365,4391,4476`）。

| 条件（build / 実行経路） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Qwen3.6 GPU engine の hybrid expert 経路 | 診断を行わず、通常の peer 配置・比較規則 | 空文字、`0`、`1`、`false` など、値を問わず設定済み | なし（環境変数が未設定の場合のみ無効） |
| それ以外（peer tier が開かない経路を含む） | 効果なし | 環境変数単体では機能を開始しない | ― |

## 有効になる条件

- Qwen3.6 engine の実行経路であること。GPU engine target は `q36_engine.cu` を使い、`STRATA_HIP_GFX906` の場合はその target を作りません（`engine/cmake/strata_gpu_engine.cmake:565-579`）。
- hybrid expert placement に入ること。全 routed expert が card 0 の VRAM に収まり通常配置で早期 return する場合、この変数の配置判定には到達しません。expert が収まらず hybrid になる場合でも、`STRATA_NATIVE_EXPERTS=OFF` の build は CPU expert pool がなく、配置関数がエラーを返します（`engine/src/qwen35/q36_engine.cu:4318-4337`）。
- `--peer-device N` で `N >= 1` を指定し、peer tier の allocation が成功すること。未指定時の `peer_device` は `-1` で、peer tier は開きません（`engine/src/qwen35/q36_engine.cu:4077-4080,5341,5388,5470-5472`）。peer tier の補助 buffer を確保できない場合は `peer.comp` が null となり、batch の entry は CPU pool に残ります（`engine/src/qwen35/q36_engine.cu:4220-4235`）。
- 比較は peer share が実際に entry を受け持ち、`cpu_chk` が確保されたときだけ行います。比較対象は peer に存在し、かつ card 0 の slot にもある routed entry です。peer が受け持つ entry がない場合は比較ログも出ません（`engine/src/qwen35/q36_engine.cu:3216-3227,3364-3375`）。
- peer share は main layer の decode batch 経路です。prompt chunk は通常この経路に入らず、`T > hybrid_t` または Hadamard / `gu_nib` layout の layer も peer share が entry を返しません（`engine/src/qwen35/q36_engine.cu:3191-3208`）。
- `STRATA_Q36_PEER_VERIFY` は比較用 `cpu_chk` buffer の確保条件にも使われます。両変数が設定されている場合、`STRATA_Q36_PEER_VS_C0` 側の分岐が比較対象を「両 GPU にある row」にします（`engine/src/qwen35/q36_engine.cu:3364-3392,4476-4477`）。

## 実行時の詳細

環境値は expert 配置時の `place_experts` で読み、設定済みなら `open_peer_tier` に `keep0=0` を渡します。peer tier は card 0 が保持する expert を除外せず、profile の順位（profile がなければ expert index 順）から slot を埋めます。実際に二重計算・比較されるのは peer tier と card 0 の slot の両方に存在する expert の entry です。profile 順や slot 数によっては両 tier の共通 expert が一部だけの場合もあります（`engine/src/qwen35/q36_engine.cu:4081-4084,4182-4199,4391-4392`）。

peer share の最初の実行時に別の function-local `static const bool` が環境値を読み、その後はその値を cache します。同様に比較処理側にも独立した static cache があります。配置判定はその都度読みますが、ソース内にこの環境変数を書き換える箇所はありません（`engine/src/qwen35/q36_engine.cu:3210,3365,4391`）。

batch entry の routing 後、peer GPU が row を計算して `cpu_out` に返します。比較時は card 0 の stream を同期し、card 0 の `eparts` row を host の比較 buffer にコピーしてから、peer と card 0 の各 float を `!=` で比較します。row 内に異なる値が一つでもあれば mismatch row とし、差分の絶対値最大値を更新します。比較結果は `chk_rows` / `chk_bad` に集計されます（`engine/src/qwen35/q36_engine.cu:3364-3395`）。

## ログと測定値

不一致がある場合、または比較ログがまだ 8 回未満の場合、stderr に次の形式で出力します（実際の値は実行時に埋められます）。

```text
strata-q36: peer rows L%zu: %d entries%s, %d differ (max %.3g); total %lld of %lld rows
```

この設定による mismatch だけで終了・失敗にするコードはありません。`n_peer == 0` の batch や比較 buffer がない場合はこの比較ログを出しません。測定値について Strata の資料に本環境変数の条件付き benchmark は見つかりません（`engine/src/qwen35/q36_engine.cu:3224-3227,3364-3401`）。

配置時に peer device が存在しない、slot を確保できない、または device memory の情報取得に失敗すると、`place_experts` は `false` を返し、engine は `strata-q36: <理由>` を stderr に出して終了コード 1 を返します。例外として peer の補助 buffer allocation の失敗は診断出力の後に peer share を無効にして続行します（`engine/src/qwen35/q36_engine.cu:4121-4144,4149-4154,4229-4235,5523-5526`）。

`docs/DETAILS.md` と `docs/SECOND_GPU.md` は peer tier の一般的な説明を載せていますが、この診断変数や比較値の測定条件は記載していません。ここでは上記のソース実装で確認できる診断処理だけを記述しています。

## 根拠

- build target と CPU pool macro: `engine/cmake/strata_gpu_engine.cmake:565-579`
- peer share の設定有無判定と entry の振り分け: `engine/src/qwen35/q36_engine.cu:3191-3227`
- 配置時の `keep0` と hybrid 条件: `engine/src/qwen35/q36_engine.cu:4318-4344,4387-4396`
- 比較 buffer の確保、比較処理、stderr ログ: `engine/src/qwen35/q36_engine.cu:3325-3401,4470-4478`
- `--peer-device` の既定値・引数設定: `engine/src/qwen35/q36_engine.cu:5341,5388-5391,5470-5473`
