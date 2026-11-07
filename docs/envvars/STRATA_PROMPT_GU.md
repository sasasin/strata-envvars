# `STRATA_PROMPT_GU`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。Strata リポジトリの作業ツリーは `main` (`## main...origin/main`) で、未コミット変更はありません。外部ライブラリの環境変数は対象外です。

## 役割

Metal の window prompt 経路で、MoE の gate/up v3 grouped GEMM に使うタイル寸法 `(TM,TN,TK,SG)` を上書きします。ソースコメントでは test tooling とされています。GPU 機能全般や通常の decode 経路を切り替える変数ではありません。

値は `PromptBufs::gu3[0..3]` に読み込まれ、gate/up 用 Metal 関数名、dispatch の threadgroup 幅、間接引数メタデータの計算に使われます。したがって、対応する v3 経路では kernel variant と処理形状が変わります (`metal/src/engine/prompt_chain.inc:65-72,134-135,447-462`)。

## 値と判定

初期値は `16,32,32,4` です。環境変数が設定されていれば、`sscanf(e, "%d,%d,%d,%d", ...)` で最大 4 個の整数を読みます。文字列全体の厳密な検証、範囲チェック、clamp、明示的なエラー処理はありません (`metal/src/engine/prompt_chain.inc:67-70`)。

| 値 | 実装上の結果 |
|---|---|
| 未設定 | 初期値 `(16,32,32,4)`。ただし `STRATA_PROMPT_V6` の条件成立時は下記の既定上書きがある。 |
| 空文字 | 変数は設定済みだが `sscanf` は整数を割り当てず、初期値が残る。`STRATA_PROMPT_V6` の既定上書きも抑止する。 |
| `20,64,32,2` | 4 個すべてを整数として読み、4 値を置き換える。 |
| `20,64` | 先頭 2 値だけ置き換え、残りはその時点の値を保つ。 |
| `20x,64,32,2` | `%d` が先頭の `20` を読み取った後、次にカンマが必要な箇所で一致に失敗するため、先頭値だけが更新される。 |
| `x,64,32,2` | 最初の整数変換に失敗し、4 値とも変更されない。 |
| `20,64,32,2,999` または後続文字付き | 4 変換後の余りは確認せず無視する。 |

`%d` が受け付ける値に正負の整数を含みます。許容範囲やゼロ・負数の検査はこの読み取り箇所にはありません。無効そうな寸法を設定した場合の結果は、生成される関数名、Metal pipeline 作成または dispatch で失敗する可能性がありますが、ここでは値検証・fallback・専用エラーを実装していません (`metal/src/engine/prompt_chain.inc:447-477`)。

## 有効になる条件

- `STRATA_METAL_PROMPT=window` を指定していないこと。
- streaming window ではないこと。
- prompt の行数が `STRATA_METAL_PROMPT_MIN` 以上であること（未設定時 32）。この条件を満たさない場合や `window` モードでは 8-row window の経路です (`metal/src/engine/prompt_chain.inc:8-11`; `metal/src/engine/window.cpp:3593-3599`)。
- `pc_setup()` がまだ同じかそれ以上の chunk 用バッファを用意していないこと。既存バッファで足りる場合は setup が早期 return し、環境値を読み直しません (`metal/src/engine/prompt_chain.inc:49-51`)。
- MoE prompt が v3 expert kernel を使うこと。`b.v3e` は `COOP_K4` 判定が真で、layer 0 の gate expert tensor type が 144 未満の場合に限り真です。そうでなければ `gu3[0]` は `PC_TM` に戻され、dispatch は v2 kernel へ進むため、この変数による `gu3` 設定は kernel selection に使われません (`metal/src/engine/prompt_chain.inc:26-47,61-72,447-459`)。
- `STRATA_PROMPT_V6` の既定は `4`、設定時は `atoi` で整数化されます。全 48 層の gate/up/down tensor type が v6 対応集合に含まれ、かつ `ms >= 2` の場合、v6 kernel が有効になり、`TM` は 16 に強制されます。`STRATA_PROMPT_GU` が未設定なら `TN,TK,SG` は `(16,32,4)` に設定されます。変数が設定済みなら、空文字も含めてこの既定上書きを抑え、環境から得た値（読み取りに失敗した場合は初期値）を残します。v6 のときも `gu3[1..3]` は関数名と dispatch に使われます (`metal/src/engine/prompt_chain.inc:73-89,449-462`)。
- `STRATA_PROMPT_DN` は down projection 用です。独立して読み取られますが、`dn3[0] != tm` の場合は stderr に警告し、down 側の `TM` を gate/up の `tm` に合わせます。これは gate/up 側の値が実際に使われる場面で tile height を共通化する相互作用です (`metal/src/engine/prompt_chain.inc:69-72,91`)。

この経路は Metal 実装です。CUDA/HIP/SYCL 経路でこの名前を読む参照は確認できませんでした。

## 実行時の詳細

`prompt_run_rows()` は window が存在しない場合に失敗し、条件に合う非 streaming prompt を `Window::prompt()` へ渡します。`Window::prompt()` は `pc_setup()` を呼び、そこで既定値を設定した後に環境を読みます (`metal/src/engine/window.cpp:3593-3599`; `metal/src/engine/prompt_chain.inc:49-70`)。従って値はリクエストごとに常時再評価されるのではなく、prompt setup が必要になった時点で読み取られ、その `PromptBufs` 設定の利用中に反映されます。

`b.v3e` が真の場合、`gu3` の全値から `mm_gu3_<type>_<TM>_<TN>_<TK>_<SG>` という関数名を作って pipeline を取得し、`SG` から `tg[0] = 32 * SG` を設定します。v6 では `mm_gu6_<type>_<ms>_<TN>_<TK>_<SG>` を選びます。さらに `TN * SG` を用いて indirect metadata の値を計算します (`metal/src/engine/prompt_chain.inc:134-135,447-462`)。pipeline は `Window::P()` が名前を key にして cache します (`metal/src/engine/window.cpp:272-278`)。

行数が少ない、window prompt を明示、streaming prompt のいずれかでは `prompt_chain.inc` のこの設定箇所に到達しません。streaming 経路は別の prompt GEMM 初期化を使い、`STRATA_PROMPT_GU` はそこで参照されません (`metal/src/engine/window.cpp:3598-3605,2905-2929`)。

明示的な環境値を示す専用ログや、値の妥当性を知らせる警告はありません。tile height の相互不一致については `strata metal: STRATA_PROMPT_GU/DN tile heights differ: using %d for both` を stderr に出し、down 側を補正します (`metal/src/engine/prompt_chain.inc:91`)。pipeline 生成など下流の失敗が起きた場合の処理は Metal context の実装に依存するため、この変数固有の終了コードやエラー文言は確認できません。

## 根拠

- 全参照の検索結果: `metal/src/engine/prompt_chain.inc:66,69,87,91`。値の読み取りは 69 行、v6 の設定有無判定は 87 行、警告は 91 行です。
- prompt 経路と適用条件: `metal/src/engine/window.cpp:3593-3605`; `metal/src/engine/prompt_chain.inc:8-11,49-72`。
- v3/v6 の kernel 選択と設定値の使用: `metal/src/engine/prompt_chain.inc:73-91,134-135,447-477`。
- pipeline cache: `metal/src/engine/window.cpp:272-278`。
