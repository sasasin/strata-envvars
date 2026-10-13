# `STRATA_VERIFY_NO_HOST`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有の SYCL 実装と同梱ラッパー・セットアップ。外部ドライバーの動作は含めない。

## 役割

SYCL の検証 window で、各 layer の CPU/GPU doorbell handshake（GPU が layer ごとにホストへ計画・応答を求め、ホストが処理するやりとり）を省き、ホスト側は GPU の window 全体が終わるまで待つ経路を選びます。SYCL engine の `strata-sycl.sh` は通常この変数を `1` にして起動します。i915 の Arc A-series 向けセットアップは `0` を設定します。

これは単独で device plan を有効にする変数ではありません。`STRATA_VERIFY_DEVICE_PLAN` などで device plan が使われるか、cache の常駐状態、ミラーの有無が実際の処理を左右します。

## 値と判定

engine の C++ 実装は `getenv()` の値を、空でなく、文字列全体が `"0"` でない場合に有効とします。数値 parse はせず、文字列の完全一致で比較します。

| 値 | engine 内の判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0` | 無効 |
| `1`、`2`、`false`、`00`、`0abc`、空白を含む文字列など | 有効（空でなく、全体が `0` と一致しないため） |

SYCL wrapper `sycl/serve/strata-sycl.sh` は既定値として `1` を用意し、親環境の `STRATA_*` があればその値で上書きします。値が空文字または厳密に `0` の場合は Docker に渡しません。したがって、wrapper 経由で `0` または空文字を指定したとき、engine では未設定となり無効です。`sycl/setup_intel.py` は i915 driver の設定に `STRATA_VERIFY_NO_HOST=0` を書き、wrapper の既定を打ち消します。

根拠: `sycl/src/core/verify.cpp:808,2185`; `sycl/src/program/generate.cpp:4874,4975`; `sycl/serve/strata-sycl.sh:25-35`; `sycl/setup_intel.py:193-202`。

## 有効になる条件

- 変数が有効でも、device plan は別の `STRATA_VERIFY_DEVICE_PLAN` が設定され、その `atoi()` 結果が 0 でない場合に限り有効です。ただし、全expertがVRAM cacheに常駐する window では `all_resident_` が優先され、`device_plan_` は false になります。device plan の割り当てに失敗した場合も無効化されます。詳細は `sycl/src/core/verify.cpp:701-729,748-771`。
- device plan を使う場合も、GPU cache または pinned host mirror から必要なexpertを処理できることが必要です。起動時にVRAMにもmirrorにもないexpertが見つかり、この変数が有効なら engine は `strata generate: REFUSED: ...` をstderrへ出して、その生成を開始せず `return 2` します。ホストmirrorはfirst stageしか覆わないlayer splitでは、後段stageにcache slot不足がある場合も拒否します（`sycl/src/program/generate.cpp:4872-4879,4970-4988`）。
- 起動時にmissがあり、`--adapt-every` と `--adapt-swaps` が指定されている場合、移動後のexpertをGPUもmirrorも持たずGPUが応答待ちになるのを避けるため、stderrに `strata generate: adaptive swaps off: ...` を出し、`o.adapt_every = 0` とします（`sycl/src/program/generate.cpp:4881-4888`）。
- 同梱wrapperの既定 `1` はxe driver向けです。i915向けセットアップは `0` を設定します。docs/INTEL.mdもB70 (`xe`) とA750 (`i915`) で値を分けています（`sycl/serve/strata-sycl.sh:22-35`; `sycl/setup_intel.py:193-202`; `docs/INTEL.md:680-703`）。

## 実行時の詳細

検証windowの実行後、通常経路は各layerについてGPUのsequence flagを待ち、CPU expert処理と計画公開を進めます。`no_host` が真ならそのlayer単位ループを実行せず、直後の `cs_->wait()` でGPUのwindow全体が完了するのを待ちます（`sycl/src/core/verify.cpp:2180-2203,2302-2310`）。この分岐の読み取りは関数内の `static const bool` なので、初回評価後は同じプロセス内で環境を変更しても再評価されません。

同じ名前は `Verifier::record_window()` のstatic判定にも使われ、`STRATA_VERIFY_LEAN` が無効でなく、device plan が有効で、step hook・remote expert経路・always-publish・stepped実行がない場合、不要なdoorbell publish/wait等のgraph nodeを省く条件になります（`sycl/src/core/verify.cpp:803-809`）。この lean 判定もstatic値を含み、初回評価後に環境値を読み直しません。

`sycl/src/program/generate.cpp` の開始前チェックは各箇所で環境を読み、起動可否とadaptive swapsを決めます。`Verifier` のstatic判定とは異なる読み取りタイミングです。wrapperはengine起動前に親環境と設定をまとめてコンテナへ渡すため、engine起動時点の値がこれらの判定に使われます（`sycl/serve/strata-sycl.sh:10-13,25-42`）。

## 文書との照合

`docs/INTEL.md` は、xeではこの変数を有効にして全window待ちを使い、i915では無効にしてCPUがVRAM外expertを処理する構成を説明しています（`docs/INTEL.md:242-249,680-703,757-760`）。コードにもi915向けに `0` を設定する処理があります。

`docs/DETAILS.md:830` には `STRATA_VERIFY_LEAN` によるgraph node削減で「-2%」という記載がありますが、その一行だけでは測定環境や比較条件を特定できないため、この値を一般的な性能効果としては扱いません。今回確認したコードから性能差は導けません。

## 根拠

- 値判定とlean条件: `sycl/src/core/verify.cpp:803-809`
- device plan と全常駐判定: `sycl/src/core/verify.cpp:701-729,748-771`
- layerごとのhost処理を飛ばし、window完了を待つ経路: `sycl/src/core/verify.cpp:2180-2203,2302-2310`
- VRAM/mirror miss の拒否とadaptive swaps無効化: `sycl/src/program/generate.cpp:4872-4888`
- 後段layer-split missの拒否: `sycl/src/program/generate.cpp:4970-4988`
- wrapperの既定・値の引き継ぎ: `sycl/serve/strata-sycl.sh:10-13,22-42`
- i915向け設定: `sycl/setup_intel.py:193-202`
- docs照合: `docs/INTEL.md:242-249,680-703,757-760`; `docs/DETAILS.md:830`
