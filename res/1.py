from fileinput import filename

from roboflow import Roboflow

rf = Roboflow(api_key="V4QzjerEevgLAIYUEjOh")
workspace = rf.workspace("animal-detect-pofbw")
#print(workspace)
workspace.deploy_model(
  model_type="yolov11",
  model_path="./runs",
  project_ids=["animal-detect-pbebr"],
  model_name="my_custom_model",
  filename = "predict.pt"
)